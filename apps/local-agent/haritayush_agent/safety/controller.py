from __future__ import annotations

import threading
import time
import math
import os
from dataclasses import dataclass

from haritayush_agent.core.config import Settings
from haritayush_agent.safety.audit import AuditLog
from haritayush_agent.workload.demo_job import SimulatedDemoJob


@dataclass
class ActiveAction:
    command: dict
    before: dict
    applied_monotonic: float
    baseline_temp_c: float
    result_recorded: bool = False
    rolled_back: bool = False
    rollback_reason: str | None = None


class SafetyController:
    def __init__(self, settings: Settings, audit: AuditLog, job, emit_audit, *,
                 backend_online=lambda: True, allow_estimated_for_tests: bool = False,
                 simulated_temperature: bool = False, fresh_reading_provider=None) -> None:
        self.settings, self.audit, self.job, self.emit_audit = settings, audit, job, emit_audit
        self.backend_online = backend_online
        self.allow_estimated_for_tests = allow_estimated_for_tests
        self.simulated_temperature = simulated_temperature
        self.fresh_reading_provider = fresh_reading_provider
        if allow_estimated_for_tests and type(job) is not SimulatedDemoJob:
            raise ValueError("the estimated-temperature override is test-only and requires the built-in state-only workload")
        self.active: ActiveAction | None = None
        self.last_action_monotonic = float("-inf")
        self.kill = threading.Event()
        self._lock = threading.RLock()

    def process(self, command: dict, latest_reading: dict | None, reading_time: float | None) -> None:
        command_id = str(command.get("id", ""))
        if not command_id or self.audit.command_seen(command_id):
            return
        # Persist id before processing so a crash or replay cannot apply it twice.
        from datetime import datetime, timezone
        self.audit.remember_command(command_id, datetime.now(timezone.utc).isoformat())
        kind = command.get("type")
        if not self.backend_online():
            self._reject(command, "Backend is unreachable; actions are disabled")
            return
        if kind in ("start_job", "stop_job"):
            self._presenter_command(command, kind, latest_reading, reading_time)
            return
        if kind != "cpu_cap":
            self._reject(command, "Unsupported command type")
            return
        with self._lock:
            if not self._approved(command):
                self._reject(command, "approved check failed: operator approval missing or malformed")
                return
            if not self._right_target():
                self._reject(command, "right_target check failed: cap target is not exclusively the agent-owned demo job")
                return
            if not self._cap_in_bounds(command.get("cap_pct")):
                self._reject(command, f"in_bounds check failed: cap is outside configured {self.settings.cap_min_pct}-{self.settings.cap_max_pct}% bounds")
                return
            if self.fresh_reading_provider is not None:
                try:
                    latest_reading, reading_time = self.fresh_reading_provider()
                except Exception as exc:
                    self._reject(command, f"fresh_data check failed: could not refresh reading: {exc}")
                    return
            now = time.monotonic()
            if not self._fresh_data(latest_reading, reading_time, now):
                self._reject(command, "fresh_data check failed: latest reading is stale or CPU temperature is not measured")
                return
            if not self._one_at_a_time(now):
                self._reject(command, "one_at_a_time check failed: another action is active, cooldown has not passed, or kill switch is active")
                return
            before = _before(latest_reading)
            try:
                self.job.apply_cap(int(command["cap_pct"]))
            except Exception as exc:
                self._reject(command, f"Windows job cap failed: {exc}")
                return
            self.active = ActiveAction(command, before, now, float(latest_reading["cpu_temp_c"]))
            self.last_action_monotonic = now
            self.emit_audit(self._event("action_applied", command, "CPU cap applied after all five safety checks passed", before))

    def _cap_in_bounds(self, raw) -> bool:
        return (isinstance(raw, (int, float)) and not isinstance(raw, bool) and math.isfinite(raw)
                and self.settings.cap_min_pct <= raw <= self.settings.cap_max_pct)

    def _approved(self, command: dict) -> bool:
        return self._has_approval(command)

    def _right_target(self) -> bool:
        owned = getattr(self.job, "owns_target", False)
        if callable(owned):
            owned = owned()
        return bool(owned) and os.getpid() not in getattr(self.job, "owned_pids", set())

    def _fresh_data(self, reading: dict | None, reading_time: float | None, now: float) -> bool:
        if reading is None or reading_time is None or not 0 <= now - reading_time < 10:
            return False
        status = reading.get("temp_status")
        accepted_status = status == "measured" or (
            self.allow_estimated_for_tests and self.simulated_temperature and status == "estimated")
        return accepted_status and reading.get("cpu_temp_c") is not None

    def _one_at_a_time(self, now: float) -> bool:
        return self.active is None and now - self.last_action_monotonic >= self.settings.cooldown_s and not self.kill.is_set()

    @staticmethod
    def _has_approval(command: dict) -> bool:
        from datetime import datetime, timedelta, timezone
        approver, action_id, approved_at = command.get("approved_by"), command.get("action_id"), command.get("approved_at")
        if not isinstance(approver, str) or not approver.strip() or not isinstance(action_id, str) or not action_id.strip():
            return False
        if not isinstance(approved_at, str):
            return False
        try:
            timestamp = datetime.fromisoformat(approved_at.replace("Z", "+00:00"))
        except ValueError:
            return False
        if timestamp.tzinfo is None:
            return False
        return timestamp <= datetime.now(timezone.utc).replace(microsecond=0) + timedelta(seconds=60)

    def _presenter_command(self, command: dict, kind: str, reading: dict | None, reading_time: float | None) -> None:
        with self._lock:
            try:
                if kind == "start_job":
                    if self.kill.is_set():
                        raise RuntimeError("kill switch is active")
                    self.job.start()
                else:
                    self.job.stop()
                    if self.active:
                        self._rollback_active("Demo job stopped; cap removed", reading, reading_time,
                                               target_already_stopped=True)
                self.emit_audit(self._event("job_started" if kind == "start_job" else "job_stopped", command,
                                            "Demo job started" if kind == "start_job" else "Demo job stopped"))
            except Exception as exc:
                self._reject(command, f"Could not {kind.replace('_', ' ')}: {exc}")

    def monitor(self, reading: dict | None, reading_time: float | None = None) -> None:
        with self._lock:
            if not self.active:
                return
            elapsed = time.monotonic() - self.active.applied_monotonic
            action = self.active
            if action.rolled_back:
                if not action.result_recorded and elapsed >= self.settings.settle_s:
                    self._record_result(action, reading, reading_time)
                if action.result_recorded:
                    self.active = None
                return
            temp = (reading.get("cpu_temp_c") if reading and self._temperature_usable(reading) else None)
            risen = temp is not None and temp >= self.active.baseline_temp_c + self.settings.temperature_rise_rollback_c
            measurement_lost = temp is None
            target_stopped = not self.job.running
            expired = elapsed >= self.settings.action_timeout_s
            if risen or measurement_lost or target_stopped or expired or self.kill.is_set():
                if self.kill.is_set():
                    reason = "Local kill switch used; cap removed"
                elif measurement_lost:
                    reason = "Measured temperature became unavailable; safety rollback"
                elif target_stopped:
                    reason = "Demo job exited; active cap cleared"
                elif risen:
                    reason = "Temperature rose after the cap; safety rollback"
                else:
                    reason = "Action timer expired; cap removed"
                self._rollback_active(reason, reading, reading_time, target_already_stopped=target_stopped)
                if elapsed >= self.settings.settle_s and self.active and not self.active.result_recorded:
                    self._record_result(self.active, reading, reading_time)
                if self.active and self.active.result_recorded:
                    self.active = None
                return
            if (elapsed >= self.settings.settle_s and not self.active.result_recorded and temp is not None
                    and reading_time is not None and reading_time > self.active.applied_monotonic):
                self._record_result(self.active, reading, reading_time)

    def _record_result(self, action: ActiveAction, reading: dict | None, reading_time: float | None) -> None:
        usable = (reading is not None and self._temperature_usable(reading)
                  and reading_time is not None and reading_time > action.applied_monotonic)
        after = _before(reading) if usable else None
        if not usable:
            if self.simulated_temperature:
                reason = "No post-action estimated simulated temperature available for the after reading"
            else:
                reason = "No post-action measured temperature available for the after reading"
        elif action.rollback_reason:
            label = self._temperature_label(reading)
            reason = f"{label} result at settle period after rollback: {action.rollback_reason}"
        elif reading.get("temp_status") == "estimated":
            reason = "Estimated simulated result after the settle period"
        else:
            reason = "Measured result after the settle period"
        self.emit_audit(self._event("action_result", action.command, reason, action.before, after))
        action.result_recorded = True

    def kill_switch(self, reading: dict | None = None, reading_time: float | None = None) -> None:
        with self._lock:
            self.kill.set()
            self.job.stop()
            if self.active:
                action = self.active
                if not action.rolled_back:
                    self._rollback_active("Local kill switch used; workload stopped and cap removed",
                                           reading, reading_time, target_already_stopped=True)
                self.emit_audit(self._event("kill_switch", action.command, "Local kill switch used; all actions halted", action.before))
            else:
                self.emit_audit(self._event("kill_switch", {}, "Local kill switch used; all actions halted"))

    def _rollback_active(self, reason: str, reading: dict | None, reading_time: float | None,
                         *, target_already_stopped: bool = False) -> None:
        action = self.active
        if action is None or action.rolled_back:
            return
        if not target_already_stopped:
            self.job.remove_cap()
        self.emit_audit(self._event("rolled_back", action.command, reason, action.before))
        action.rolled_back = True
        action.rollback_reason = reason
        elapsed = time.monotonic() - action.applied_monotonic
        if not action.result_recorded and elapsed >= self.settings.settle_s:
            self._record_result(action, reading, reading_time)
        if action.result_recorded:
            self.active = None

    def _reject(self, command: dict, reason: str) -> None:
        self.emit_audit(self._event("action_rejected", command, reason))

    def _event(self, event: str, command: dict, reason: str, before=None, after=None) -> dict:
        from datetime import datetime, timezone
        if self.simulated_temperature:
            reason = f"DEV ONLY: CPU temperature is estimated simulation, never measured. {reason}"
        return {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
                "site_id": self.settings.site_id, "event": event,
                "action_id": command.get("action_id"), "actor": "agent",
                "approver": command.get("approved_by"), "reason": reason,
                "before": before, "after": after}

    def _temperature_usable(self, reading: dict) -> bool:
        return (reading.get("cpu_temp_c") is not None and
                (reading.get("temp_status") == "measured" or
                 (self.allow_estimated_for_tests and self.simulated_temperature
                  and reading.get("temp_status") == "estimated")))

    @staticmethod
    def _temperature_label(reading: dict | None) -> str:
        return "Estimated simulated" if reading and reading.get("temp_status") == "estimated" else "Measured"


def _before(reading: dict | None) -> dict | None:
    if reading is None:
        return None
    return {"cpu_pct": reading.get("cpu_pct"), "cpu_temp_c": reading.get("cpu_temp_c")}

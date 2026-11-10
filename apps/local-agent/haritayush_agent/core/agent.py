from __future__ import annotations

import logging
import sys
import threading
import time

from haritayush_agent.communication.client import BackendClient
from haritayush_agent.core.config import Settings
from haritayush_agent.safety.audit import AuditLog
from haritayush_agent.safety.controller import SafetyController
from haritayush_agent.telemetry.sensors import SensorReader, SimulatedSensorReader
from haritayush_agent.workload.demo_job import DemoJob, SimulatedDemoJob

log = logging.getLogger("haritayush_agent")


class Agent:
    def __init__(self, settings: Settings, *, dev_mock: bool = False,
                 allow_estimated_for_tests: bool = False) -> None:
        self.settings = settings
        settings.state_dir.mkdir(parents=True, exist_ok=True)
        self.client = BackendClient(settings.backend_url, settings.request_timeout_s)
        self.outbox = AuditLog(settings.state_dir / "agent-state.sqlite3")
        self.sensors = SimulatedSensorReader(settings.site_id) if dev_mock else SensorReader(settings.site_id)
        self.job = SimulatedDemoJob() if dev_mock else DemoJob()
        if allow_estimated_for_tests and not dev_mock:
            raise ValueError("--dev-allow-estimated-cap is only valid with --dev-mock")
        if dev_mock:
            print("\n*** DEV ONLY: CPU temperature is simulated and labelled estimated, never measured. ***\n",
                  file=sys.stderr, flush=True)
        if allow_estimated_for_tests:
            print("\n*** LOUD WARNING: TEST OVERRIDE ENABLED. This is a simulated job; no OS CPU cap can be applied. ***\n",
                  file=sys.stderr, flush=True)
        self.stop_event = threading.Event()
        self.network_thread: threading.Thread | None = None
        self.reading_lock = threading.Lock()
        self.flush_lock = threading.Lock()
        self.latest_reading: dict | None = None
        self.latest_reading_monotonic: float | None = None
        self.was_disconnected = False
        self.retry_after = 0.0
        self.controller = SafetyController(
            settings, self.outbox, self.job, self._record_audit,
            backend_online=lambda: self.client.is_online,
            allow_estimated_for_tests=allow_estimated_for_tests,
            simulated_temperature=dev_mock,
            fresh_reading_provider=self._fresh_action_reading,
        )

    def run(self) -> None:
        log.info("Starting agent for %s; backend=%s; local kill file=%s", self.settings.site_id,
                 self.settings.backend_url, self.kill_file)
        self.network_thread = threading.Thread(target=self._network_loop, name="HaritAyushNetwork", daemon=True)
        self.network_thread.start()
        while not self.stop_event.is_set():
            started = time.monotonic()
            if self.kill_file.exists():
                latest_reading, reading_time = self._reading_snapshot()
                self.controller.kill_switch(latest_reading, reading_time)
                try:
                    self.kill_file.unlink()
                except OSError:
                    pass
            reading = self.sensors.read(job_running=self.job.running, cap_pct=self.job.cap_pct)
            with self.reading_lock:
                self.latest_reading = reading.payload
                self.latest_reading_monotonic = reading.taken_monotonic
            self.controller.monitor(reading.payload, reading.taken_monotonic)
            self.outbox.buffer_reading(reading.payload)
            self.stop_event.wait(max(0.0, self.settings.interval_s - (time.monotonic() - started)))

    @property
    def kill_file(self):
        return self.settings.state_dir / "KILL"

    def stop(self) -> None:
        self.stop_event.set()
        if self.network_thread is not None:
            self.network_thread.join(timeout=self.settings.request_timeout_s * 2 + 1)
        latest_reading, reading_time = self._reading_snapshot()
        if self.controller.active:
            self.controller.kill_switch(latest_reading, reading_time)
            # Graceful shutdown still honors the settle interval for the single action result.
            while self.controller.active and not self.controller.active.result_recorded:
                elapsed = time.monotonic() - self.controller.active.applied_monotonic
                remaining = self.settings.settle_s - elapsed
                if remaining > 0:
                    time.sleep(min(self.settings.interval_s, remaining))
                reading = self.sensors.read(job_running=self.job.running, cap_pct=self.job.cap_pct)
                self.controller.monitor(reading.payload, reading.taken_monotonic)
                self.outbox.buffer_reading(reading.payload)
        else:
            self.job.stop()
        self._flush_outbox()

    def _record_audit(self, event: dict) -> None:
        self.outbox.audit(event)
        self._flush_outbox()

    def _flush_outbox(self) -> None:
        if not self.flush_lock.acquire(blocking=False):
            return
        try:
            # One sequence preserves order across readings and audit events.
            for seq, kind, payload in self.outbox.pending_outbox(limit=100):
                delivery_key = f"{self.settings.site_id}:{kind}:{seq}"
                sent = (self.client.post_audit(payload, delivery_key) if kind == "audit"
                        else self.client.post_reading(payload, delivery_key))
                if not sent:
                    self._mark_gap()
                    return
                self.outbox.mark_outbox_delivered(seq)
            if self.was_disconnected:
                self.was_disconnected = False
                self.retry_after = 0.0
                self.outbox.audit(self._event("data_gap", "Backend connection restored; buffered data delivery resumed"))
        except (OSError, TimeoutError, ValueError) as exc:
            log.warning("Backend unavailable; readings are buffered and actions remain local-only: %s", exc)
            self._mark_gap()
        finally:
            self.flush_lock.release()

    def _network_loop(self) -> None:
        next_poll = 0.0
        while not self.stop_event.is_set():
            now = time.monotonic()
            if now >= self.retry_after:
                self._flush_outbox()
            # Do not consume one-shot commands before the first fresh reading exists.
            if now >= next_poll and self.latest_reading is not None:
                self._poll_commands()
                next_poll = time.monotonic() + self.settings.interval_s
            self.stop_event.wait(0.1)

    def _mark_gap(self) -> None:
        self.retry_after = time.monotonic() + 0.5
        if not self.was_disconnected:
            self.was_disconnected = True
            self.outbox.audit(self._event("data_gap", "Backend unreachable; readings buffered and no new commands accepted"))

    def _poll_commands(self) -> None:
        try:
            commands = self.client.pending_commands(self.settings.site_id)
        except (OSError, TimeoutError, ValueError) as exc:
            log.warning("Command poll failed: %s", exc)
            self._mark_gap()
            return
        if not self.client.is_online:
            self._mark_gap()
            return
        latest_reading, reading_time = self._reading_snapshot()
        for command in commands:
            try:
                self.controller.process(command, latest_reading, reading_time)
            except Exception:
                log.exception("Command processing failed")

    def _reading_snapshot(self) -> tuple[dict | None, float | None]:
        with self.reading_lock:
            return self.latest_reading, self.latest_reading_monotonic

    def _fresh_action_reading(self) -> tuple[dict, float]:
        reading = self.sensors.read(job_running=self.job.running, cap_pct=self.job.cap_pct)
        with self.reading_lock:
            self.latest_reading = reading.payload
            self.latest_reading_monotonic = reading.taken_monotonic
        # Persist the just-before-action sample so the audit's before values are traceable.
        self.outbox.buffer_reading(reading.payload)
        return reading.payload, reading.taken_monotonic

    def _event(self, event: str, reason: str) -> dict:
        from datetime import datetime, timezone
        return {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
                "site_id": self.settings.site_id, "event": event, "action_id": None,
                "actor": "agent", "approver": None, "reason": reason,
                "before": None, "after": None}

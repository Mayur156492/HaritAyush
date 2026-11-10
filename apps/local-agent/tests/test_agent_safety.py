from __future__ import annotations

import os
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from haritayush_agent.core.config import Settings
from haritayush_agent.safety.audit import AuditLog
from haritayush_agent.safety.controller import SafetyController
from haritayush_agent.telemetry.sensors import SensorReader, SimulatedSensorReader
from haritayush_agent.workload.demo_job import DemoJob, SimulatedDemoJob


class FakeJob:
    is_simulated = False

    def __init__(self, running=True, owns_target=True):
        self.running = running
        self.owns_target = owns_target
        self.owned_pids = set()
        self.cap_pct = 100
        self.applied = []
        self.stopped = False

    def apply_cap(self, pct):
        self.applied.append(pct)
        self.cap_pct = pct

    def remove_cap(self):
        self.cap_pct = 100

    def start(self):
        self.running = True

    def stop(self):
        self.running = False
        self.cap_pct = 100
        self.stopped = True


class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.audit = AuditLog(Path(self.tmp.name) / "state.sqlite3")
        self.settings = Settings(state_dir=Path(self.tmp.name), cooldown_s=0, settle_s=30)
        self.job = FakeJob()
        self.events = []
        self.controller = SafetyController(self.settings, self.audit, self.job, self.events.append)
        self.reading = {"cpu_pct": 55.0, "cpu_temp_c": 72.0, "temp_status": "measured"}
        self.command = {"id": "c1", "type": "cpu_cap", "cap_pct": 50, "action_id": "a1",
                        "approved_by": "Operator", "approved_at": datetime.now(timezone.utc).isoformat()}

    def tearDown(self):
        self.audit.db.close()
        self.tmp.cleanup()

    def run_command(self, command=None, reading=None, reading_time=None):
        self.controller.process(command or self.command,
                                reading if reading is not None else self.reading,
                                time.monotonic() if reading_time is None else reading_time)

    def test_approved_check_pass_and_fail(self):
        self.run_command()
        self.assertEqual(self.job.applied, [50])
        self.run_command(dict(self.command, id="c2", approved_at="bad"))
        self.assertEqual(self.job.applied, [50])
        self.assertIn("approved check failed", self.events[-1]["reason"])

    def test_right_target_check_pass_and_fail(self):
        self.run_command()
        self.assertEqual(self.job.applied, [50])
        job = FakeJob(owns_target=False)
        controller = SafetyController(self.settings, self.audit, job, self.events.append)
        controller.process(dict(self.command, id="c2"), self.reading, time.monotonic())
        self.assertEqual(job.applied, [])
        self.assertIn("right_target check failed", self.events[-1]["reason"])

    def test_in_bounds_check_pass_and_fail(self):
        self.run_command()
        self.assertEqual(self.job.applied, [50])
        job = FakeJob()
        controller = SafetyController(self.settings, self.audit, job, self.events.append)
        controller.process(dict(self.command, id="c2", cap_pct=81), self.reading, time.monotonic())
        self.assertEqual(job.applied, [])
        self.assertIn("in_bounds check failed", self.events[-1]["reason"])

    def test_before_values_use_fresh_reading_immediately_before_apply(self):
        fresh = {"cpu_pct": 67.0, "cpu_temp_c": 74.0, "temp_status": "measured"}
        controller = SafetyController(self.settings, self.audit, self.job, self.events.append,
                                      fresh_reading_provider=lambda: (fresh, time.monotonic()))
        stale = {"cpu_pct": 12.0, "cpu_temp_c": 40.0, "temp_status": "measured"}
        controller.process(self.command, stale, time.monotonic() - 5)
        applied = next(event for event in self.events if event["event"] == "action_applied")
        self.assertEqual(applied["before"], {"cpu_pct": 67.0, "cpu_temp_c": 74.0})

    def test_fresh_data_check_pass_and_fail(self):
        self.run_command()
        self.assertEqual(self.job.applied, [50])
        job = FakeJob()
        controller = SafetyController(self.settings, self.audit, job, self.events.append)
        controller.process(dict(self.command, id="c2"), self.reading, time.monotonic() - 11)
        self.assertEqual(job.applied, [])
        self.assertIn("fresh_data check failed", self.events[-1]["reason"])
        unavailable = dict(self.reading, cpu_temp_c=None, temp_status="unavailable")
        controller.process(dict(self.command, id="c3"), unavailable, time.monotonic())
        self.assertIn("fresh_data check failed", self.events[-1]["reason"])
        estimated = dict(self.reading, temp_status="estimated")
        controller.process(dict(self.command, id="c4"), estimated, time.monotonic())
        self.assertIn("fresh_data check failed", self.events[-1]["reason"])

    def test_one_at_a_time_check_pass_and_fail_for_active_and_cooldown(self):
        self.run_command()
        self.assertEqual(self.job.applied, [50])
        self.run_command(dict(self.command, id="c2", action_id="a2"))
        self.assertIn("one_at_a_time check failed", self.events[-1]["reason"])
        self.controller.active = None
        self.controller.settings = Settings(state_dir=Path(self.tmp.name), cooldown_s=30)
        self.controller.last_action_monotonic = time.monotonic()
        self.run_command(dict(self.command, id="c3", action_id="a3"))
        self.assertIn("one_at_a_time check failed", self.events[-1]["reason"])

    def test_backend_offline_disables_commands(self):
        job = FakeJob()
        controller = SafetyController(self.settings, self.audit, job, self.events.append,
                                      backend_online=lambda: False)
        controller.process(self.command, self.reading, time.monotonic())
        self.assertEqual(job.applied, [])
        self.assertIn("Backend is unreachable", self.events[-1]["reason"])

    def test_duplicate_command_id_is_not_applied_twice(self):
        self.run_command()
        self.run_command()
        self.assertEqual(self.job.applied, [50])

    def test_temperature_rise_and_timer_roll_back(self):
        self.run_command()
        self.controller.active.applied_monotonic -= 31
        self.controller.monitor({"cpu_pct": 60, "cpu_temp_c": 75, "temp_status": "measured"}, time.monotonic())
        self.assertEqual(self.job.cap_pct, 100)
        self.assertTrue(any(event["event"] == "rolled_back" for event in self.events))
        self.run_command(dict(self.command, id="c2", action_id="a2"))
        self.controller.settings = Settings(state_dir=Path(self.tmp.name), cooldown_s=0, action_timeout_s=10)
        self.controller.active.applied_monotonic -= 11
        self.controller.monitor(self.reading, time.monotonic())
        self.assertEqual(self.job.cap_pct, 100)
        self.assertEqual(self.events[-1]["event"], "rolled_back")

    def test_lost_temperature_and_job_stop_roll_back(self):
        self.run_command()
        self.controller.active.applied_monotonic -= 31
        unavailable = {"cpu_pct": 54, "cpu_temp_c": None, "temp_status": "unavailable"}
        self.controller.monitor(unavailable, time.monotonic())
        self.assertEqual(self.job.cap_pct, 100)
        self.assertTrue(any("temperature became unavailable" in event["reason"] for event in self.events))

        self.run_command(dict(self.command, id="c2", action_id="a2"))
        self.controller.process({"id": "stop-1", "type": "stop_job"}, self.reading, time.monotonic())
        self.assertFalse(self.job.running)
        self.assertEqual(self.job.cap_pct, 100)
        self.assertTrue(any(event["event"] == "rolled_back" and event["action_id"] == "a2"
                            for event in self.events))

    def test_kill_switch_during_active_cap_logs_rollback_and_kill(self):
        self.run_command()
        self.controller.kill_switch(self.reading, time.monotonic())
        self.assertFalse(self.job.running)
        self.assertEqual([e["event"] for e in self.events[-2:]], ["rolled_back", "kill_switch"])

    def test_kill_switch_stops_job_and_always_logs(self):
        self.controller.kill_switch()
        self.assertTrue(self.job.stopped)
        self.assertEqual(self.events[-1]["event"], "kill_switch")

    def test_estimated_override_is_simulation_only_and_loudly_labelled(self):
        with self.assertRaises(ValueError):
            SafetyController(self.settings, self.audit, FakeJob(), self.events.append,
                             allow_estimated_for_tests=True, simulated_temperature=True)
        job = SimulatedDemoJob()
        job.start()
        controller = SafetyController(self.settings, self.audit, job, self.events.append,
                                      allow_estimated_for_tests=True, simulated_temperature=True)
        est = {"cpu_pct": 20, "cpu_temp_c": 62.0, "temp_status": "estimated"}
        controller.process(dict(self.command, id="dev-cap"), est, time.monotonic())
        self.assertEqual(job.cap_pct, 50)
        self.assertIn("estimated simulation, never measured", self.events[-1]["reason"])
        self.assertEqual(est["temp_status"], "estimated")


class TelemetryTests(unittest.TestCase):
    def test_reading_has_exact_contract_fields_and_null_unavailable_temp(self):
        with patch("haritayush_agent.telemetry.sensors._read_cpu_temperature", return_value=None):
            payload = SensorReader().read(job_running=False, cap_pct=100).payload
        self.assertEqual(set(payload), {"site_id", "ts", "cpu_pct", "mem_pct", "cpu_temp_c", "temp_status", "unavailable", "demo_job"})
        self.assertTrue(payload["ts"].endswith("Z"))
        self.assertEqual(payload["temp_status"], "unavailable")
        self.assertIsNone(payload["cpu_temp_c"])
        self.assertEqual(set(payload["unavailable"]), {"gpu_temp", "fan_rpm", "inlet_temp", "humidity", "power_w", "cpu_temp"})
        self.assertEqual(payload["demo_job"], {"running": False, "cap_pct": 100})

    def test_dev_temperature_is_estimated_and_never_measured(self):
        payload = SimulatedSensorReader().read(job_running=True, cap_pct=100).payload
        self.assertEqual(payload["temp_status"], "estimated")
        self.assertIsNotNone(payload["cpu_temp_c"])
        self.assertNotIn("cpu_temp", payload["unavailable"])

    def test_site_and_cap_range_are_settings(self):
        with patch.dict(os.environ, {"HARITAYUSH_SITE_ID": "test-site",
                                     "HARITAYUSH_CAP_MIN_PCT": "35",
                                     "HARITAYUSH_CAP_MAX_PCT": "75"}):
            settings = Settings.from_env()
        self.assertEqual(settings.site_id, "test-site")
        self.assertEqual((settings.cap_min_pct, settings.cap_max_pct), (35, 75))
        self.assertEqual(Settings().settle_s, 45)

    def test_test_override_cannot_construct_real_windows_job(self):
        with tempfile.TemporaryDirectory() as temp:
            audit = AuditLog(Path(temp) / "state.sqlite3")
            try:
                with self.assertRaises(ValueError):
                    SafetyController(Settings(state_dir=Path(temp)), audit, DemoJob(), lambda event: None,
                                     allow_estimated_for_tests=True, simulated_temperature=True)
            finally:
                audit.db.close()

    def test_local_outbox_preserves_interleaved_order_and_marks_delivery(self):
        with tempfile.TemporaryDirectory() as temp:
            audit = AuditLog(Path(temp) / "state.sqlite3")
            try:
                audit.buffer_reading({"ts": "2026-11-10T10:00:00Z"})
                audit.audit({"ts": "2026-11-10T10:00:01Z", "event": "data_gap"})
                queue = audit.pending_outbox()
                self.assertEqual([row[1] for row in queue], ["reading", "audit"])
                audit.mark_outbox_delivered(queue[0][0])
                self.assertEqual(audit.pending_count(), 1)
            finally:
                audit.db.close()


if __name__ == "__main__":
    unittest.main()

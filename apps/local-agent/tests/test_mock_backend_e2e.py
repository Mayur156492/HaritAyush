from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stderr
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from haritayush_agent.core.agent import Agent
from haritayush_agent.core.config import Settings
from haritayush_agent.mock_backend import EVENTS, MockBackend


def _request(base_url: str, path: str, method="GET", payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    request = Request(base_url + path, data=data, method=method,
                      headers={"Content-Type": "application/json", "Accept": "application/json"})
    with urlopen(request, timeout=2) as response:
        raw = response.read()
        return response.status, json.loads(raw) if raw else {}


def _wait_for(predicate, timeout: float, message: str):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.1)
    raise AssertionError(message)


def _queue(base_url: str, kind: str, **fields):
    status, result = _request(base_url, "/dev/commands", "POST", {"type": kind, **fields})
    if status != 201:
        raise AssertionError(f"mock command injection returned {status}")
    return result["command"]


class MockContractTests(unittest.TestCase):
    def test_required_endpoints_and_commands_are_delivered_once(self):
        with MockBackend(port=0) as backend:
            status, health = _request(backend.url, "/health")
            self.assertEqual(status, 200)
            self.assertTrue(health["ok"])
            command = _queue(backend.url, "start_job")
            status, pending = _request(backend.url, "/commands/pending?site_id=laptop-01")
            self.assertEqual(status, 200)
            self.assertEqual(pending["commands"], [command])
            _, pending_again = _request(backend.url, "/commands/pending?site_id=laptop-01")
            self.assertEqual(pending_again["commands"], [])
            _, audit = _request(backend.url, "/audit")
            self.assertEqual(audit["entries"], [])

    def test_idempotency_header_prevents_duplicate_audit_posts(self):
        with MockBackend(port=0) as backend:
            payload = {"ts": _now(), "site_id": "laptop-01", "event": "action_rejected",
                       "action_id": None, "actor": "agent", "approver": None,
                       "reason": "test", "before": None, "after": None}
            key = "laptop-01:audit:42"
            request = Request(backend.url + "/audit", data=json.dumps(payload).encode(), method="POST",
                              headers={"Content-Type": "application/json", "Idempotency-Key": key})
            with urlopen(request) as first:
                first_body = json.loads(first.read())
            with urlopen(request) as second:
                second_body = json.loads(second.read())
            self.assertEqual(first_body, second_body)
            self.assertEqual(len(backend.state.audit), 1)


class AgentEndToEndTests(unittest.TestCase):
    def test_dev_agent_full_loop_validation_kill_and_offline_replay(self):
        with tempfile.TemporaryDirectory() as temp, MockBackend(port=0) as backend:
            settings = Settings(
                backend_url=backend.url,
                state_dir=Path(temp),
                interval_s=2.0,
                request_timeout_s=0.4,
                cooldown_s=0,
                settle_s=30,
                action_timeout_s=35,
            )
            warnings = StringIO()
            with redirect_stderr(warnings):
                agent = Agent(settings, dev_mock=True, allow_estimated_for_tests=True)
            warning_text = warnings.getvalue()
            self.assertIn("simulated and labelled estimated, never measured", warning_text)
            self.assertIn("no OS CPU cap can be applied", warning_text)

            errors = []
            worker = threading.Thread(target=lambda: _run_agent(agent, errors), daemon=True)
            worker.start()
            try:
                _wait_for(lambda: bool(backend.state.readings), 8, "agent did not post an initial reading")
                self.assertEqual(backend.state.readings[0]["temp_status"], "estimated")
                self.assertNotIn("measured", {r["temp_status"] for r in backend.state.readings})

                _queue(backend.url, "start_job")
                _wait_for(lambda: any(e["event"] == "job_started" for e in backend.state.audit),
                          8, "start_job was not applied")
                self.assertTrue(agent.job.running)

                _queue(backend.url, "cpu_cap", id="reject-unapproved", cap_pct=50, action_id="a-unapproved")
                _queue(backend.url, "cpu_cap", id="reject-range", cap_pct=90, action_id="a-range",
                       approved_by="Operator", approved_at=_now())
                _wait_for(lambda: len([e for e in backend.state.audit if e["event"] == "action_rejected"]) >= 2,
                          8, "invalid commands were not rejected")
                rejects = [e for e in backend.state.audit if e["event"] == "action_rejected"]
                self.assertTrue(any("approved check failed" in e["reason"] for e in rejects))
                self.assertTrue(any("in_bounds check failed" in e["reason"] for e in rejects))
                self.assertEqual(agent.job.cap_pct, 100)

                approved = _queue(backend.url, "cpu_cap", id="approved-cap", cap_pct=50, action_id="a-approved",
                                  approved_by="Aditya", approved_at=_now())
                _wait_for(lambda: any(e["event"] == "action_applied" and e["action_id"] == "a-approved"
                                      for e in backend.state.audit),
                          10, "approved cap was not applied")
                applied = next(e for e in backend.state.audit if e["event"] == "action_applied"
                               and e["action_id"] == "a-approved")
                self.assertEqual(agent.job.cap_pct, 50)
                self.assertEqual(applied["approver"], "Aditya")
                self.assertIsNotNone(applied["before"]["cpu_temp_c"])
                self.assertIn("estimated simulation, never measured", applied["reason"])

                # Even if a delivered command is injected a second time, its durable ID blocks reapplication.
                _queue(backend.url, "cpu_cap", id=approved["id"], cap_pct=50, action_id="a-approved",
                       approved_by="Aditya", approved_at=_now())

                _wait_for(lambda: any(e["event"] == "action_result" and e["action_id"] == "a-approved"
                                      for e in backend.state.audit),
                          38, "action_result did not arrive after the settle interval")
                result = next(e for e in backend.state.audit if e["event"] == "action_result"
                              and e["action_id"] == "a-approved")
                self.assertEqual(result["approver"], "Aditya")
                self.assertIsNotNone(result["before"]["cpu_temp_c"])
                self.assertIsNotNone(result["after"]["cpu_temp_c"])
                self.assertIn("estimated simulation, never measured", result["reason"])
                self.assertEqual(len([e for e in backend.state.audit if e["event"] == "action_result"
                                      and e["action_id"] == "a-approved"]), 1)

                _wait_for(lambda: any(e["event"] == "rolled_back" and e["action_id"] == "a-approved"
                                      for e in backend.state.audit),
                          10, "action timer did not roll the cap back")
                self.assertEqual(agent.job.cap_pct, 100)

                # The local kill file halts the simulated workload and is logged even without an active cap.
                agent.kill_file.parent.mkdir(parents=True, exist_ok=True)
                agent.kill_file.touch()
                _wait_for(lambda: any(e["event"] == "kill_switch" for e in backend.state.audit),
                          6, "kill switch event was not logged")
                self.assertFalse(agent.job.running)
                _queue(backend.url, "start_job", id="start-after-kill")
                _wait_for(lambda: any(e["event"] == "action_rejected"
                                      and "kill switch is active" in e["reason"]
                                      for e in backend.state.audit),
                          6, "kill switch did not block a later start command")
                self.assertFalse(agent.job.running)

                # Disconnect the mock, ensure readings and the gap event stay in the durable local outbox.
                backend.stop()
                _wait_for(lambda: agent.client.is_online is False and agent.outbox.pending_count() > 0,
                          8, "offline state was not detected or buffered")
                self.assertTrue(any(kind == "audit" and item["event"] == "data_gap"
                                    for _, kind, item in agent.outbox.pending_outbox(1000)))
                reconnect_order = [f"{settings.site_id}:{kind}:{seq}"
                                   for seq, kind, _ in agent.outbox.pending_outbox(1000)]
                self.assertTrue(reconnect_order)

                backend.start()
                _wait_for(lambda: any(e["event"] == "data_gap" and "connection restored" in e["reason"]
                                      for e in backend.state.audit),
                          12, "buffered data was not replayed after reconnect")
                replayed_order = [key for key in backend.state.received_order if key in set(reconnect_order)]
                self.assertEqual(replayed_order, reconnect_order)
                self.assertEqual(len(backend.state.received_order), len(set(backend.state.received_order)))
                self.assertEqual(len(backend.state.idempotency), len(backend.state.received_order))
                _wait_for(lambda: agent.outbox.pending_count() == 0, 5, "outbox did not drain")
                self.assertFalse(errors, f"agent thread failed: {errors}")
                self.assertTrue(backend.state.audit)
                self.assertTrue({entry["event"] for entry in backend.state.audit}.issubset(EVENTS))
                required_audit_fields = {"ts", "site_id", "event", "action_id", "actor", "approver", "reason", "before", "after"}
                self.assertTrue(all(required_audit_fields.issubset(entry) for entry in backend.state.audit))
            finally:
                agent.stop()
                worker.join(timeout=3)
                agent.outbox.db.close()


def _run_agent(agent: Agent, errors: list[BaseException]) -> None:
    try:
        agent.run()
    except BaseException as exc:
        errors.append(exc)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


if __name__ == "__main__":
    unittest.main()

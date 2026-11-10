"""DEV ONLY contract mock for the Person 2 agent; not a production backend."""

from __future__ import annotations

import argparse
import json
import math
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

EVENTS = {"action_applied", "action_rejected", "action_result", "rolled_back", "kill_switch",
          "data_gap", "job_started", "job_stopped"}
READING_FIELDS = {"site_id", "ts", "cpu_pct", "mem_pct", "cpu_temp_c", "temp_status", "unavailable", "demo_job"}


class MockBackendState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.readings: list[dict] = []
        self.audit: list[dict] = []
        self.commands: list[tuple[str, dict]] = []
        self.idempotency: set[tuple[str, str]] = set()
        self.idempotency_responses: dict[tuple[str, str], dict] = {}
        self.received_order: list[str] = []
        self.next_audit_id = 1
        self.next_command_id = 1

    def queue_command(self, command: dict, site_id: str = "laptop-01") -> dict:
        command = dict(command)
        command.setdefault("id", f"mock-c{self.next_command_id}")
        command.setdefault("issued_at", _now())
        with self.lock:
            self.commands.append((site_id, command))
            self.next_command_id += 1
        return command


class _Server(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address, state: MockBackendState | None = None):
        self.state = state or MockBackendState()
        super().__init__(address, _Handler)


class _Handler(BaseHTTPRequestHandler):
    server: _Server

    def log_message(self, fmt, *args):
        return

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length) or b"{}")
        if not isinstance(body, dict):
            raise ValueError("JSON body must be an object")
        return body

    def _send(self, status: int, payload: dict | None = None) -> None:
        raw = json.dumps(payload or {}, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        parsed = urlsplit(self.path)
        if parsed.path == "/health":
            with self.server.state.lock:
                latest = self.server.state.readings[-1] if self.server.state.readings else None
            age = None
            if latest:
                try:
                    stamp = datetime.fromisoformat(latest["ts"].replace("Z", "+00:00"))
                    age = max(0, int((datetime.now(timezone.utc) - stamp).total_seconds()))
                except (ValueError, TypeError):
                    age = None
            self._send(200, {"ok": True, "data_mode": "live", "last_reading_age_s": age})
            return
        if parsed.path == "/audit":
            query = parse_qs(parsed.query)
            limit = max(1, min(int(query.get("n", ["50"])[0]), 1000))
            with self.server.state.lock:
                entries = list(reversed(self.server.state.audit[-limit:]))
            self._send(200, {"entries": entries})
            return
        if parsed.path == "/readings/recent":
            site_id = parse_qs(parsed.query).get("site_id", ["laptop-01"])[0]
            with self.server.state.lock:
                readings = [r for r in self.server.state.readings if r["site_id"] == site_id][-120:]
            self._send(200, {"site_id": site_id, "readings": readings})
            return
        if parsed.path == "/commands/pending":
            site_id = parse_qs(parsed.query).get("site_id", ["laptop-01"])[0]
            with self.server.state.lock:
                delivered = [command for target, command in self.server.state.commands if target == site_id]
                self.server.state.commands = [(target, command) for target, command in self.server.state.commands
                                              if target != site_id]
            self._send(200, {"commands": delivered})
            return
        self._send(404, {"error": {"code": "not_found", "message": "Unknown endpoint"}})

    def do_POST(self):
        path = urlsplit(self.path).path
        try:
            payload = self._body()
        except (ValueError, json.JSONDecodeError) as exc:
            self._send(400, {"error": {"code": "invalid_field", "message": str(exc)}})
            return
        if path == "/readings":
            if set(payload) != READING_FIELDS:
                self._send(400, {"error": {"code": "invalid_field", "message": "reading fields do not match contract"}})
                return
            if payload.get("temp_status") not in {"measured", "estimated", "unavailable"}:
                self._send(400, {"error": {"code": "invalid_field", "message": "invalid temp_status"}})
                return
            if (payload["temp_status"] == "unavailable") != (payload["cpu_temp_c"] is None):
                self._send(400, {"error": {"code": "invalid_field", "message": "temperature null/status mismatch"}})
                return
            if (not isinstance(payload.get("site_id"), str) or not isinstance(payload.get("unavailable"), list)
                    or not isinstance(payload.get("demo_job"), dict)
                    or set(payload["demo_job"]) != {"running", "cap_pct"}
                    or not isinstance(payload["demo_job"].get("running"), bool)):
                self._send(400, {"error": {"code": "invalid_field", "message": "invalid site, unavailable, or demo_job"}})
                return
            try:
                timestamp = datetime.fromisoformat(payload["ts"].replace("Z", "+00:00"))
                percentages = (float(payload["cpu_pct"]), float(payload["mem_pct"]))
                temp_value = None if payload["cpu_temp_c"] is None else float(payload["cpu_temp_c"])
                cap_value = float(payload["demo_job"]["cap_pct"])
            except (KeyError, TypeError, ValueError, AttributeError):
                self._send(400, {"error": {"code": "invalid_field", "message": "invalid reading values"}})
                return
            if (not payload["ts"].endswith("Z") or timestamp.tzinfo is None
                    or any(not math.isfinite(v) or not 0 <= v <= 100 for v in percentages)
                    or not math.isfinite(cap_value) or not 0 <= cap_value <= 100
                    or (temp_value is not None and (not math.isfinite(temp_value) or not 0 <= temp_value <= 120))):
                self._send(400, {"error": {"code": "invalid_field", "message": "reading value out of range"}})
                return
            with self.server.state.lock:
                if not self._already_seen_locked("reading"):
                    self.server.state.readings.append(payload)
                    self.server.state.received_order.append(self.headers.get("Idempotency-Key", "reading-without-key"))
            self._send(201, {"ok": True})
            return
        if path == "/audit":
            if payload.get("event") not in EVENTS or payload.get("actor") != "agent":
                self._send(400, {"error": {"code": "invalid_field", "message": "invalid audit event"}})
                return
            with self.server.state.lock:
                key = self.headers.get("Idempotency-Key", "")
                composite = ("audit", key)
                if not self._already_seen_locked("audit"):
                    entry = dict(payload)
                    entry["audit_id"] = f"mock-a{self.server.state.next_audit_id}"
                    self.server.state.next_audit_id += 1
                    self.server.state.audit.append(entry)
                    self.server.state.idempotency_responses[composite] = {"ok": True, "audit_id": entry["audit_id"]}
                    self.server.state.received_order.append(key or f"audit:{entry['audit_id']}")
                response = self.server.state.idempotency_responses.get(composite, {"ok": True, "audit_id": "duplicate"})
            self._send(201, response)
            return
        if path == "/dev/commands":
            if payload.get("type") not in {"cpu_cap", "start_job", "stop_job"}:
                self._send(400, {"error": {"code": "invalid_field", "message": "unsupported command type"}})
                return
            command = self.server.state.queue_command(payload, payload.get("site_id", "laptop-01"))
            self._send(201, {"command": command})
            return
        self._send(404, {"error": {"code": "not_found", "message": "Unknown endpoint"}})

    def _already_seen_locked(self, kind: str) -> bool:
        key = self.headers.get("Idempotency-Key")
        if not key:
            return False
        composite = (kind, key)
        if composite in self.server.state.idempotency:
            return True
        self.server.state.idempotency.add(composite)
        return False


class MockBackend:
    def __init__(self, host: str = "127.0.0.1", port: int = 8001) -> None:
        self._host, self._port = host, port
        self._state = MockBackendState()
        self.server = _Server((host, port), self._state)
        self._port = self.server.server_address[1]
        self.thread: threading.Thread | None = None

    @property
    def url(self) -> str:
        host, port = self.server.server_address
        return f"http://{host}:{port}"

    @property
    def state(self) -> MockBackendState:
        return self._state

    def start(self) -> "MockBackend":
        if self.thread is None:
            if self.server.fileno() == -1:
                self.server = _Server((self._host, self._port), self._state)
            self.thread = threading.Thread(target=self.server.serve_forever, name="HaritAyushMockBackend", daemon=True)
            self.thread.start()
        return self

    def stop(self) -> None:
        if self.thread is not None:
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(timeout=2)
            self.thread = None

    def __enter__(self):
        return self.start()

    def __exit__(self, *_exc):
        self.stop()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def main() -> int:
    parser = argparse.ArgumentParser(description="DEV ONLY HaritAyush API mock backend")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()
    server = _Server((args.host, args.port))
    print(f"DEV ONLY mock backend listening at http://{args.host}:{args.port}")
    print("Command injection helper: POST /dev/commands")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

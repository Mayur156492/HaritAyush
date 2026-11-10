from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request


class BackendClient:
    def __init__(self, base_url: str, timeout_s: float = 2.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self._online = False
        self._state_lock = threading.Lock()

    @property
    def is_online(self) -> bool:
        with self._state_lock:
            return self._online

    def request(self, method: str, path: str, body: dict | None = None,
                idempotency_key: str | None = None) -> tuple[int, dict | None]:
        data = json.dumps(body, separators=(",", ":")).encode("utf-8") if body is not None else None
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        request = urllib.request.Request(
            self.base_url + path, data=data, method=method,
            headers=headers,
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                raw = response.read()
                with self._state_lock:
                    self._online = 200 <= response.status < 300
                return response.status, json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            with self._state_lock:
                self._online = False
            try:
                payload = json.loads(raw) if raw else None
            except json.JSONDecodeError:
                payload = None
            return exc.code, payload
        except (urllib.error.URLError, TimeoutError, OSError):
            with self._state_lock:
                self._online = False
            raise

    def post_reading(self, reading: dict, idempotency_key: str | None = None) -> bool:
        status, _ = self.request("POST", "/readings", reading, idempotency_key)
        return status in (200, 201, 202)

    def post_audit(self, event: dict, idempotency_key: str | None = None) -> bool:
        status, _ = self.request("POST", "/audit", event, idempotency_key)
        return status in (200, 201, 202)

    def pending_commands(self, site_id: str) -> list[dict]:
        from urllib.parse import quote
        status, payload = self.request("GET", f"/commands/pending?site_id={quote(site_id)}")
        if status != 200 or not isinstance(payload, dict):
            return []
        commands = payload.get("commands", [])
        return commands if isinstance(commands, list) else []

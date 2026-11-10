from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path


class AuditLog:
    """Durable local append-only event journal and delivery outbox."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS audit (
              seq INTEGER PRIMARY KEY AUTOINCREMENT, event_json TEXT NOT NULL,
              delivered INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS readings (
              seq INTEGER PRIMARY KEY AUTOINCREMENT, reading_json TEXT NOT NULL,
              delivered INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS commands (command_id TEXT PRIMARY KEY, seen_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS outbox (
              seq INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL,
              payload_json TEXT NOT NULL, source_seq INTEGER NOT NULL,
              delivered INTEGER NOT NULL DEFAULT 0,
              UNIQUE(kind, source_seq)
            );
        """)
        self._migrate_pending_rows()
        self.db.commit()

    def audit(self, event: dict) -> None:
        with self._lock, self.db:
            payload = json.dumps(event, separators=(",", ":"))
            cursor = self.db.execute("INSERT INTO audit(event_json) VALUES (?)", (payload,))
            self.db.execute("INSERT INTO outbox(kind,payload_json,source_seq) VALUES ('audit',?,?)",
                            (payload, cursor.lastrowid))

    def buffer_reading(self, reading: dict) -> None:
        with self._lock, self.db:
            payload = json.dumps(reading, separators=(",", ":"))
            cursor = self.db.execute("INSERT INTO readings(reading_json) VALUES (?)", (payload,))
            self.db.execute("INSERT INTO outbox(kind,payload_json,source_seq) VALUES ('reading',?,?)",
                            (payload, cursor.lastrowid))

    def pending_outbox(self, limit: int = 100) -> list[tuple[int, str, dict]]:
        with self._lock:
            rows = self.db.execute(
                "SELECT seq,kind,payload_json FROM outbox WHERE delivered=0 ORDER BY seq LIMIT ?", (limit,)
            ).fetchall()
            return [(seq, kind, json.loads(data)) for seq, kind, data in rows]

    def pending_count(self) -> int:
        with self._lock:
            return int(self.db.execute("SELECT COUNT(*) FROM outbox WHERE delivered=0").fetchone()[0])

    def mark_outbox_delivered(self, seq: int) -> None:
        with self._lock, self.db:
            row = self.db.execute("SELECT kind,source_seq FROM outbox WHERE seq=?", (seq,)).fetchone()
            if row is None:
                return
            kind, source_seq = row
            self.db.execute("UPDATE outbox SET delivered=1 WHERE seq=?", (seq,))
            table, column = ("audit", "event_json") if kind == "audit" else ("readings", "reading_json")
            self.db.execute(f"UPDATE {table} SET delivered=1 WHERE seq=?", (source_seq,))

    def _migrate_pending_rows(self) -> None:
        rows = []
        for kind, table, column in (("audit", "audit", "event_json"), ("reading", "readings", "reading_json")):
            for source_seq, payload in self.db.execute(
                    f"SELECT seq,{column} FROM {table} WHERE delivered=0").fetchall():
                try:
                    timestamp = json.loads(payload).get("ts", "")
                except (json.JSONDecodeError, AttributeError):
                    timestamp = ""
                rows.append((timestamp, kind, source_seq, payload))
        for _, kind, source_seq, payload in sorted(rows, key=lambda item: item[0]):
            self.db.execute("INSERT OR IGNORE INTO outbox(kind,payload_json,source_seq) VALUES (?,?,?)",
                            (kind, payload, source_seq))

    def pending_audits(self, limit: int = 100) -> list[tuple[int, dict]]:
        with self._lock:
            rows = self.db.execute("SELECT seq,event_json FROM audit WHERE delivered=0 ORDER BY seq LIMIT ?", (limit,)).fetchall()
            return [(seq, json.loads(data)) for seq, data in rows]

    def pending_readings(self, limit: int = 100) -> list[tuple[int, dict]]:
        with self._lock:
            rows = self.db.execute("SELECT seq,reading_json FROM readings WHERE delivered=0 ORDER BY seq LIMIT ?", (limit,)).fetchall()
            return [(seq, json.loads(data)) for seq, data in rows]

    def mark_delivered(self, table: str, seq: int) -> None:
        if table not in {"audit", "readings"}:
            raise ValueError("invalid outbox table")
        with self._lock, self.db:
            self.db.execute(f"UPDATE {table} SET delivered=1 WHERE seq=?", (seq,))

    def command_seen(self, command_id: str) -> bool:
        with self._lock:
            return self.db.execute("SELECT 1 FROM commands WHERE command_id=?", (command_id,)).fetchone() is not None

    def remember_command(self, command_id: str, ts: str) -> None:
        with self._lock, self.db:
            self.db.execute("INSERT OR IGNORE INTO commands(command_id,seen_at) VALUES (?,?)", (command_id, ts))

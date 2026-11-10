"""
Replay service for HaritAyush backend.

Loads a fixed JSONL file of synthetic readings and returns them in order,
cycling back to the start when exhausted. The replay file path is fixed
server-side — no arbitrary filesystem path may be supplied via the API.

NOTE: The dataset at data/sample/replay.jsonl is a *synthetic placeholder*
generated for the backup demo path described in the PRD (Section D6, Hour 11-12
task). Real replay data must be recorded from the laptop during the actual demo
session per PRD instructions.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Optional

from ..schemas import ReadingPayload

# Fixed server-side path — not user-configurable
REPLAY_FILE_PATH: Path = (
    Path(__file__).resolve().parents[2] / "data" / "sample" / "replay.jsonl"
)

# Module-level state protected by a lock (single-process demo)
_lock = threading.Lock()
_replay_readings: list[dict] = []
_replay_index: int = 0
_replay_started: bool = False


def load_replay_file() -> list[dict]:
    """
    Read and validate the JSONL replay file.

    Each line must be a valid ReadingPayload JSON object.
    Returns the validated list of reading dicts.

    Raises:
        FileNotFoundError: if the replay file does not exist.
        ValueError: if the file is empty or contains invalid lines.
    """
    global _replay_readings, _replay_index

    if not REPLAY_FILE_PATH.exists():
        raise FileNotFoundError(
            f"Replay file not found: {REPLAY_FILE_PATH}. "
            "Save a clean readings file at data/sample/replay.jsonl before enabling replay mode."
        )

    readings: list[dict] = []
    errors: list[str] = []

    with REPLAY_FILE_PATH.open("r", encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            try:
                data = json.loads(line)
                # Validate against ReadingPayload schema, but skip future-timestamp check
                # for replay data (timestamps are historical by design).
                # We validate field presence and types only.
                _validate_replay_line(data, lineno)
                readings.append(data)
            except json.JSONDecodeError as exc:
                errors.append(f"Line {lineno}: invalid JSON — {exc}")
            except ValueError as exc:
                errors.append(f"Line {lineno}: {exc}")

    if errors:
        raise ValueError(
            f"Replay file has {len(errors)} invalid line(s):\n" + "\n".join(errors)
        )
    if not readings:
        raise ValueError(
            f"Replay file is empty: {REPLAY_FILE_PATH}. "
            "Add at least one ReadingPayload JSON line."
        )

    with _lock:
        _replay_readings = readings
        _replay_index = 0
        _replay_started = False

    return readings


def _validate_replay_line(data: dict, lineno: int) -> None:
    """Validate required ReadingPayload fields (skipping future-ts check)."""
    required_str = {"site_id", "ts", "temp_status"}
    required_float = {"cpu_pct", "mem_pct"}
    valid_temp_statuses = {"measured", "estimated", "unavailable"}

    for field in required_str:
        if field not in data:
            raise ValueError(f"missing required field '{field}'")
        if not isinstance(data[field], str):
            raise ValueError(f"field '{field}' must be a string")

    for field in required_float:
        if field not in data:
            raise ValueError(f"missing required field '{field}'")
        if not isinstance(data[field], (int, float)):
            raise ValueError(f"field '{field}' must be numeric")

    if data["temp_status"] not in valid_temp_statuses:
        raise ValueError(
            f"temp_status must be one of {valid_temp_statuses}, "
            f"got '{data['temp_status']}'"
        )


def get_next_replay_reading() -> Optional[dict]:
    """
    Return the next reading in replay sequence and advance the index.

    Wraps cyclically so replay loops continuously.
    Returns None if no readings are loaded.
    """
    global _replay_index, _replay_started

    with _lock:
        if not _replay_readings:
            return None
        reading = _replay_readings[_replay_index]
        _replay_index = (_replay_index + 1) % len(_replay_readings)
        _replay_started = True
        return reading


def get_current_replay_reading() -> Optional[dict]:
    """
    Return the most recently served reading without advancing the index.

    Returns None if no readings are loaded.
    """
    with _lock:
        if not _replay_readings:
            return None
        # _replay_index points to the *next* reading; the current one is one back
        idx = (_replay_index - 1) % len(_replay_readings) if _replay_readings else 0
        return _replay_readings[idx]


def reset_replay_position() -> None:
    """Reset replay position to the beginning of the file."""
    global _replay_index, _replay_started
    with _lock:
        _replay_index = 0
        _replay_started = False


def get_replay_history(site_id: str = "laptop-01", n: int = 120) -> list[dict]:
    """
    Return readings from the replay buffer that have already been played.

    Returns up to n readings in chronological order (oldest to newest).
    If replay has not started delivering readings yet, returns an empty list.
    """
    with _lock:
        if not _replay_readings or not _replay_started:
            return []

        # _replay_index points to the next item to be read.
        # So readings played so far in the current cycle are:
        # If _replay_index == 0, we just wrapped after reading all len(_replay_readings) items.
        count = len(_replay_readings) if _replay_index == 0 else _replay_index
        history_slice = _replay_readings[:count]

        # Filter by site_id if present
        filtered = [r for r in history_slice if r.get("site_id") == site_id]

        # Take up to n most recent, preserving chronological order
        recent = filtered[-n:] if n < len(filtered) else filtered

        # Map to format identical to get_recent_readings
        results = []
        for idx, r in enumerate(recent, start=1):
            results.append({
                "id": idx,
                "site_id": r.get("site_id", site_id),
                "ts": r.get("ts"),
                "cpu_pct": float(r.get("cpu_pct", 0.0)),
                "mem_pct": float(r.get("mem_pct", 0.0)),
                "cpu_temp_c": r.get("cpu_temp_c"),
                "temp_status": r.get("temp_status", "measured"),
                "unavailable": r.get("unavailable"),
                "demo_job": r.get("demo_job"),
            })
        return results


def get_loaded_readings() -> list[dict]:
    """Return a copy of the currently loaded replay readings (for testing)."""
    with _lock:
        return list(_replay_readings)


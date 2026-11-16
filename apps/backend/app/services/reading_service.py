"""Service for reading telemetry storage and retrieval — synchronous."""

from __future__ import annotations

import json

from sqlalchemy import select

from app.database import engine, session_factory
from app.models import Reading, Base


def store_reading(reading: Reading) -> int:
    """Persist a validated telemetry reading to the database.

    Returns the assigned reading ID.
    """
    with session_factory() as session:
        session.add(reading)
        session.commit()
        # Refresh to make the ID available after commit
        session.refresh(reading)
        return reading.id


def get_recent_readings(site_id: str, n: int) -> list[dict]:
    """Return the n most recent readings for a device, in chronological order (oldest to newest)."""
    with session_factory() as session:
        stmt = (
            select(Reading)
            .where(Reading.site_id == site_id)
            .order_by(Reading.ts.desc(), Reading.id.desc())
            .limit(n)
        )
        result = session.execute(stmt)
        readings = list(result.scalars().all())

    # Reverse to present chronological order (oldest to newest) for charting
    readings.reverse()

    def _safe_json_loads(val: str | None):
        if not val:
            return None
        try:
            return json.loads(val)
        except Exception:
            return None

    def _format_ts(ts_val) -> str | None:
        if ts_val is None:
            return None
        if hasattr(ts_val, "isoformat"):
            return ts_val.isoformat()
        return str(ts_val)

    return [
        {
            "id": r.id,
            "site_id": r.site_id,
            "ts": _format_ts(r.ts),
            "cpu_pct": r.cpu_pct,
            "mem_pct": r.mem_pct,
            "cpu_temp_c": r.cpu_temp_c,
            "temp_status": r.temp_status,
            "unavailable": _safe_json_loads(r.unavailable),
            "demo_job": _safe_json_loads(r.demo_job),
        }
        for r in readings
    ]
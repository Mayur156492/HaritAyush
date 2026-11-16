"""GET /forecast/latest — Return latest forecast, risk, causes and recommended action.

Returns the most recent temperature forecast for the device, with 5-minute and
15-minute horizons, confidence bounds, risk assessment, explainable causes and
a pending cpu_cap recommendation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Response, status

from ...schemas import ForecastContract, ReadingRecent, CommandPending
from ...models import Reading, Forecast, Recommendation, Decision, Command, AuditRecord
from ...services.forecast_service import get_latest_forecast, evaluate_forecast_trust
from ...services.risk_service import assess_thermal_risk_and_time
from ...services.explanation_service import build_why_payload
from ...services.action_service import create_recommendation
from ...services.audit_service import record_audit
from ...services import replay_state, replay_service
from ...database import session_factory
from sqlalchemy import select


router = APIRouter(tags=["forecast"])


@dataclass
class _ReplayReading:
    """Lightweight stand-in for a Reading ORM object during replay mode."""
    site_id: str
    ts: str
    cpu_pct: float
    mem_pct: float
    cpu_temp_c: Optional[float]
    temp_status: str
    # Provide dummy id so pipeline code that accesses .id won't fail
    id: int = -1


def _get_latest_reading(site_id: str) -> Reading | None:
    """Get the latest reading for a device from the database."""
    with session_factory() as session:
        stmt = (
            select(Reading)
            .where(Reading.site_id == site_id)
            .order_by(Reading.ts.desc(), Reading.id.desc())
        )
        result = session.execute(stmt)
        return result.scalars().first()


def _get_or_compute_forecast(site_id: str, reading: Reading) -> dict:
    """Get or compute the forecast for a device."""
    return get_latest_forecast(site_id, reading)


def _get_pending_recommendation(site_id: str) -> dict | None:
    """Get the latest pending recommendation for a device, or None.

    Deterministic selection policy:
    Selects the most recently created pending recommendation (ordered by
    Recommendation.created_at DESC, Recommendation.id DESC). If multiple
    pending recommendations exist in the database, this policy deterministically
    selects the newest valid recommendation without raising MultipleResultsFound.
    """
    with session_factory() as session:
        stmt = (
            select(Recommendation)
            .where(
                Recommendation.site_id == site_id,
                Recommendation.status == "pending",
            )
            .order_by(Recommendation.created_at.desc(), Recommendation.id.desc())
        )
        result = session.execute(stmt)
        rec = result.scalars().first()
        if rec is not None:
            return {
                "rec_id": rec.id,
                "action_id": rec.action_id,
                "action_type": rec.action_type,
                "cap_pct": rec.cap_pct,
                "status": rec.status,
            }
        return None


@router.get(
    "/latest",
    response_model=ForecastContract,
    responses={
        200: {"model": ForecastContract, "description": "Latest temperature forecast"},
        204: {"description": "No telemetry readings available for device"},
    },
    summary="Get latest temperature forecast",
    description="Return the latest temperature forecast with 5-minute and 15-minute "
    "horizons, confidence bounds, risk assessment, explainable warning causes "
    "and a pending recommended action. Returns HTTP 204 when no readings are available.",
)
async def get_latest_forecast_endpoint(
    site_id: str = Query("laptop-01", description="Site/device identifier"),
):
    """Get the latest forecast for a device. Returns 204 if no readings exist."""
    in_replay = replay_state.is_replay_enabled()

    if in_replay:
        # --- REPLAY MODE ---
        # Serve the next reading from the replay sequence without touching the DB.
        replay_dict = replay_service.get_next_replay_reading()
        if replay_dict is None:
            # Replay file not loaded (should not happen if /replay endpoint used correctly)
            return Response(status_code=status.HTTP_204_NO_CONTENT)

        # Build a lightweight Reading-like object from the replay dict
        reading = _ReplayReading(
            site_id=replay_dict.get("site_id", site_id),
            ts=replay_dict.get("ts", ""),
            cpu_pct=float(replay_dict.get("cpu_pct", 0.0)),
            mem_pct=float(replay_dict.get("mem_pct", 0.0)),
            cpu_temp_c=replay_dict.get("cpu_temp_c"),
            temp_status=replay_dict.get("temp_status", "measured"),
        )
    else:
        # --- LIVE MODE ---
        reading = _get_latest_reading(site_id)
        if reading is None:
            return Response(status_code=status.HTTP_204_NO_CONTENT)

    # Get or compute forecast (same pipeline for both modes)
    forecast = _get_or_compute_forecast(site_id, reading)

    # Assess risk and time to danger
    risk_result = assess_thermal_risk_and_time(
        forecast, reading.cpu_temp_c, current_readings=[reading]
    )

    risk = risk_result["risk"]
    time_to_danger_min = risk_result["time_to_danger_min"]
    limit_c = risk_result["limit_c"]

    # Build explainable causes
    trust = forecast.get("trust", "low")
    why = build_why_payload(reading, forecast, limit_c, trust)

    if in_replay:
        # Safety: never create recommendations or commands during replay
        action = {"id": None, "type": "none", "cap_pct": None, "status": "none"}
    else:
        # Check for pending recommendation using deterministic selection policy
        rec = _get_pending_recommendation(site_id)

        if rec is not None:
            # Reuse existing pending recommendation (prevents duplicate recommendations)
            action = {
                "id": rec["action_id"] or str(rec["rec_id"]),
                "type": rec["action_type"],
                "cap_pct": rec["cap_pct"],
                "status": rec["status"],
            }
        elif risk in ("Elevated", "High", "elevated", "high"):
            # Generate new pending recommendation when risk is Elevated or High
            new_rec = create_recommendation(
                site_id=site_id,
                action_type="cpu_cap",
                cap_pct=50,
                reason=f"Temperature forecast indicates {risk} risk",
                action_id="a-17",
            )
            action = {
                "id": new_rec.action_id,
                "type": new_rec.action_type,
                "cap_pct": new_rec.cap_pct,
                "status": new_rec.status,
            }
        else:
            # Risk is Normal and no recommendation pending
            action = {
                "id": None,
                "type": "none",
                "cap_pct": None,
                "status": "none",
            }

    # Record forecast audit
    record_audit(
        site_id=site_id,
        event="forecast_generated",
        payload={
            "horizon_5": forecast.get("5", {}).get("mid"),
            "horizon_15": forecast.get("15", {}).get("mid"),
            "risk": risk,
            "trust": trust,
            "data_mode": "replay" if in_replay else "live",
        },
        outcome=None,
    )

    # Ensure time_to_danger_min is always an int (0 when no danger)
    if time_to_danger_min is None:
        time_to_danger_min = 0

    now_temp = (
        reading.cpu_temp_c
        if reading.cpu_temp_c is not None
        else (reading.cpu_pct if reading.cpu_pct is not None else 0.0)
    )

    return ForecastContract(
        ts=datetime.now(timezone.utc).isoformat(),
        now_temp_c=now_temp,
        pred={
            "5": {
                "mid": forecast["5"]["mid"],
                "lo": forecast["5"]["lo"],
                "hi": forecast["5"]["hi"],
            },
            "15": {
                "mid": forecast["15"]["mid"],
                "lo": forecast["15"]["lo"],
                "hi": forecast["15"]["hi"],
            },
        },
        limit_c=limit_c or 85.0,  # provisional demo default
        risk=risk,
        time_to_danger_min=time_to_danger_min,
        trust=trust,
        why=why,
        action=action,
        data_mode="replay" if in_replay else "live",
    )
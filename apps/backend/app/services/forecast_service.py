"""Service for temperature forecasting with persistence and learned models — synchronous."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.database import session_factory
from app.models import Reading, Forecast
from app.intelligence.forecasting.baseline_model import PersistenceBaselineModel
from app.intelligence.forecasting.learned_model import LearnedTemperatureModel


def get_latest_forecast(site_id: str, reading: Reading | None = None) -> dict:
    """Get or compute the latest temperature forecast for a device.

    Checks the DB first for an existing forecast. If none found, tries to fit
    and predict with the learned model (LearnedTemperatureModel) using historical
    observations. If historical data is insufficient or sensor readings are unavailable,
    falls back cleanly to the persistence baseline model.

    Returns forecast dict with 5-minute and 15-minute horizons.
    """
    # Check if we already have complete forecasts in the DB
    with session_factory() as session:
        stmt = (
            select(Forecast)
            .where(Forecast.site_id == site_id)
            .order_by(Forecast.created_at.desc(), Forecast.id.desc())
        )
        result = session.execute(stmt)
        existing_list = list(result.scalars().all())

    if existing_list:
        latest_ts = existing_list[0].ts
        forecast_by_horizon = {}
        for f in existing_list:
            if f.ts == latest_ts and f.horizon not in forecast_by_horizon:
                forecast_by_horizon[f.horizon] = {
                    "mid": f.mid,
                    "lo": f.lo,
                    "hi": f.hi,
                    "trust": f.trust,
                }
        if "5" in forecast_by_horizon and "15" in forecast_by_horizon:
            return forecast_by_horizon

    # Fetch recent readings to attempt learned model fitting
    with session_factory() as session:
        history_stmt = (
            select(Reading)
            .where(Reading.site_id == site_id)
            .order_by(Reading.ts.desc(), Reading.id.desc())
            .limit(100)
        )
        history_readings = list(session.execute(history_stmt).scalars().all())

    if reading is None and history_readings:
        reading = history_readings[0]

    if reading is None:
        # No data available - return low-trust fallback
        return {
            "5": {"mid": 0.0, "lo": 0.0, "hi": 0.0, "trust": "low"},
            "15": {"mid": 0.0, "lo": 0.0, "hi": 0.0, "trust": "low"},
            "trust": "low",
        }

    # Attempt learned model forecasting
    if reading.cpu_temp_c is not None and reading.temp_status == "measured" and len(history_readings) >= 15:
        learned_model = LearnedTemperatureModel()
        # History in chronological order for training
        chronological_history = list(reversed(history_readings))
        fitted = learned_model.fit(chronological_history)
        if fitted:
            prev_reading = history_readings[1] if len(history_readings) > 1 else None
            learned_pred = learned_model.predict(reading, prev_reading)
            if learned_pred is not None:
                return learned_pred

    # Safe fallback to persistence baseline model
    model = PersistenceBaselineModel()
    model.fit(
        temperature=reading.cpu_temp_c,
        timestamp=reading.ts,
        status=reading.temp_status,
    )
    return model.forecast_all()


def evaluate_forecast_trust(forecast: dict, reading: Reading) -> dict:
    """Evaluate forecast trust based on data completeness, freshness, and status.

    Per PRD §6 (B4) & §8.4:
    - High: fresh (<2 min), measured status, valid physical range.
    - Low: stale (>5 min), estimated status, or unavailable sensor values.
    """
    if reading is None or reading.cpu_temp_c is None or reading.temp_status != "measured":
        return {"trust": "low"}

    if reading.ts:
        ts = reading.ts
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        age_sec = (datetime.now(timezone.utc) - ts).total_seconds()
        if age_sec > 300:  # > 5 minutes
            return {"trust": "low"}
        if age_sec <= 120:  # <= 2 minutes
            return {"trust": "high"}

    return {"trust": "low"}


def compute_risk_and_time(
    forecast: dict,
    current_temp: float | None,
    limit_c: float | None = None,
) -> tuple[str, int | None, float | None]:
    """Assess thermal risk and time to danger from forecast.

    Per PRD §8:
    - High: temperature reaches configured limit within 15 minutes
    - Elevated: temperature reaches limit - 5°C within 15 minutes
    - Normal: neither condition is met
    - Uses upper edge of forecast confidence band for risk decisions

    Returns (risk, time_to_danger_min, limit_c).
    """
    risk = "normal"
    time_to_danger = None
    actual_limit = limit_c or 85.0  # provisional demo default

    # Get the 15-minute upper forecast value
    hi_15 = forecast.get("15", {}).get("hi", float("inf"))

    # Case 1: Current temperature already exceeds the limit
    if current_temp is not None and current_temp >= actual_limit:
        risk = "high"
        time_to_danger = 0
        return risk, time_to_danger, actual_limit

    # Case 2: Forecast upper band reaches the limit within 15 min
    if hi_15 >= actual_limit:
        risk = "high"
        # Estimate time to danger proportionally
        lo_15 = forecast.get("15", {}).get("lo", actual_limit - 5)
        temp_range = hi_15 - lo_15 if lo_15 != float("-inf") else 1.0
        excess = hi_15 - actual_limit
        if temp_range > 0 and excess > 0:
            proportion = excess / temp_range
            estimated_min = int(round(proportion * 15))
        else:
            estimated_min = 15
        time_to_danger = max(1, min(estimated_min, 15))

    # Case 3: Forecast upper band reaches limit - 5 within 15 min
    elif hi_15 >= actual_limit - 5:
        risk = "elevated"
        lo_15 = forecast.get("15", {}).get("lo", actual_limit - 10)
        temp_range = hi_15 - lo_15 if lo_15 != float("-inf") else 1.0
        excess = hi_15 - (actual_limit - 5)
        if temp_range > 0 and excess > 0:
            proportion = excess / temp_range
            estimated_min = int(round(proportion * 15))
        else:
            estimated_min = 15
        time_to_danger = max(1, min(estimated_min, 15))

    # Case 4: Normal
    else:
        risk = "normal"
        time_to_danger = None

    return risk, time_to_danger, actual_limit

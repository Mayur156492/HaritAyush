"""Verification of forecasts against observed hardware temperatures."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List

from app.models import Reading, Forecast


def verify_prediction(
    forecast_mid: float,
    forecast_target_time: datetime,
    actual_readings: List[Reading],
    tolerance_sec: int = 60,
) -> Dict[str, Any]:
    """Compare a forecast with the temperature actually observed at the target time.

    Rules:
    - Never interpolate or fabricate an observation.
    - If no reading exists within target_time +/- tolerance_sec, forecast is unverified.
    - If reading exists but temp_status != 'measured' or cpu_temp_c is None, unverified.
    - When verified, computes absolute error |pred - actual|.
    """
    if forecast_target_time.tzinfo is None:
        target = forecast_target_time.replace(tzinfo=timezone.utc)
    else:
        target = forecast_target_time

    best_reading: Optional[Reading] = None
    best_diff = float("inf")

    for r in actual_readings:
        if r.ts is None or r.cpu_temp_c is None or r.temp_status != "measured":
            continue
        r_ts = r.ts if r.ts.tzinfo is not None else r.ts.replace(tzinfo=timezone.utc)
        diff = abs((r_ts - target).total_seconds())
        if diff <= tolerance_sec and diff < best_diff:
            best_diff = diff
            best_reading = r

    if best_reading is None or best_reading.cpu_temp_c is None:
        return {
            "verified": False,
            "status": "unverified",
            "reason": "No valid measured reading within tolerance window",
            "target_time": target.isoformat(),
            "error_c": None,
            "observed_temp_c": None,
        }

    actual_temp = best_reading.cpu_temp_c
    error = abs(forecast_mid - actual_temp)

    return {
        "verified": True,
        "status": "verified",
        "target_time": target.isoformat(),
        "observed_time": best_reading.ts.isoformat(),
        "forecast_mid": round(forecast_mid, 2),
        "observed_temp_c": round(actual_temp, 2),
        "error_c": round(error, 2),
    }

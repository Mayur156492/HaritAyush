"""Thermal risk assessment engine for HaritAyush backend.

Combines temperature forecast confidence bands with current observations
to assess thermal risk and time to danger per PRD §4, §6 (B5), and §8.
"""

from __future__ import annotations

from app.intelligence.thermal_risk.thresholds import DEFAULT_DANGER_LIMIT_C, ELEVATED_MARGIN_C
from app.intelligence.thermal_risk.classification import classify_risk


def assess_thermal_risk(
    forecast: dict,
    current_temp: float | None,
    limit_c: float | None = None,
) -> dict:
    """Assess thermal risk and time to danger from a forecast and current observation.

    Per PRD §6 (B5) & §8:
    - High: upper forecast reaches limit within 15 minutes.
    - Elevated: upper forecast reaches limit - 5°C within 15 minutes.
    - Normal: neither condition is met.
    - Uses upper edge of forecast confidence band for risk decisions.
    - Computes physically grounded time to danger along the upper trajectory.
    """
    actual_limit = limit_c or DEFAULT_DANGER_LIMIT_C

    hi_15 = forecast.get("15", {}).get("hi") if isinstance(forecast.get("15"), dict) else None
    hi_5 = forecast.get("5", {}).get("hi") if isinstance(forecast.get("5"), dict) else None

    # Use upper forecast band across horizons
    available_his = [h for h in (hi_5, hi_15) if h is not None]
    max_hi = max(available_his) if available_his else None

    risk = classify_risk(max_hi, actual_limit, current_temp)

    # Calculate time to danger in minutes along upper forecast trajectory
    time_to_danger_min = 0

    if current_temp is not None and current_temp >= actual_limit:
        time_to_danger_min = 0
    elif risk == "High" and current_temp is not None and max_hi is not None:
        if max_hi > current_temp:
            rate = (max_hi - current_temp) / 15.0
            excess = actual_limit - current_temp
            if rate > 0 and excess > 0:
                time_to_danger_min = max(1, min(15, int(round(excess / rate))))
            else:
                time_to_danger_min = 1
        else:
            time_to_danger_min = 15
    elif risk == "Elevated" and current_temp is not None and max_hi is not None:
        elevated_threshold = actual_limit - ELEVATED_MARGIN_C
        if max_hi > current_temp:
            rate = (max_hi - current_temp) / 15.0
            excess = elevated_threshold - current_temp
            if rate > 0 and excess > 0:
                time_to_danger_min = max(1, min(15, int(round(excess / rate))))
            else:
                time_to_danger_min = 1
        else:
            time_to_danger_min = 15
    else:
        time_to_danger_min = 0

    return {
        "risk": risk,
        "time_to_danger_min": time_to_danger_min,
        "limit_c": actual_limit,
    }

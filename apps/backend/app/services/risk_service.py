"""Thermal risk assessment service for HaritAyush backend."""

from __future__ import annotations

from app.models import Reading, Forecast
from app.schemas import ForecastContract
from app.intelligence.thermal_risk.risk_engine import assess_thermal_risk
from app.intelligence.thermal_risk.thresholds import DEFAULT_DANGER_LIMIT_C, get_risk_thresholds


def assess_thermal_risk_and_time(
    forecast: dict,
    current_temp: float | None,
    limit_c: float | None = None,
    current_readings: list[Reading] | None = None,
) -> dict:
    """Assess thermal risk and time to danger from a forecast.

    Per PRD §4, §6 (B5), and §8:
    - High: temperature reaches configured limit within 15 minutes.
    - Elevated: temperature reaches limit - 5°C within 15 minutes.
    - Normal: neither condition is met.
    - Uses upper edge of forecast confidence band for risk decisions.
    - Returns configured danger limit (limit_c), risk level, and time to danger.
    """
    actual_limit = limit_c or DEFAULT_DANGER_LIMIT_C
    return assess_thermal_risk(forecast, current_temp, limit_c=actual_limit)


def classify_risk_level(
    risk: str,
    forecast_trust: str = "low",
) -> str:
    """Map risk assessment to the UI risk string with trust awareness.

    Per PRD §9: causes must be supported by actual data; weights must not be
    fabricated.  Risk classification must not imply that a temperature reading
    alone proves device health or lifespan.
    """
    base_map = {"high": "High", "elevated": "Elevated", "normal": "Normal"}

    if forecast_trust == "low":
        # Downgrade the displayed risk when trust is low
        if risk == "High":
            return "Elevated (low trust)"
        elif risk == "Elevated":
            return "Normal (low trust)"
        return "Normal (low trust)"

    return base_map.get(risk, "Normal")


def compute_limit_c(current_readings: list[Reading], default: float = 85.0) -> float:
    """Compute or derive the danger temperature limit.

    Per PRD §8: The danger limit must be configurable. Keep it as a provisional
    demo default until tuned on real laptop data.

    For now return the default; in a full implementation this would be stored
    per-device or read from device configuration.
    """
    return default
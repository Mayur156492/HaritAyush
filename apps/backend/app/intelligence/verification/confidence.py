"""Confidence and uncertainty estimation for temperature forecasts."""

from __future__ import annotations

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from app.models import Reading


def estimate_confidence(
    verification_history: List[Dict[str, Any]],
    current_reading: Optional[Reading],
    model_source: str = "baseline",
    mae: Optional[float] = None,
) -> Dict[str, Any]:
    """Estimate forecast confidence honestly based on verified history and data quality.

    Rules:
    - Never invent high confidence without verification evidence.
    - If telemetry is missing, stale, or incomplete, trust/confidence is low.
    - If verification history is empty or insufficient (< 5 verified points), confidence is low/uncalibrated.
    """
    if current_reading is None or current_reading.cpu_temp_c is None:
        return {
            "confidence_level": "low",
            "trust": "low",
            "calibrated": False,
            "sample_count": 0,
            "mean_error_c": None,
            "reason": "Missing current temperature observation",
        }

    if current_reading.temp_status != "measured":
        return {
            "confidence_level": "low",
            "trust": "low",
            "calibrated": False,
            "sample_count": 0,
            "mean_error_c": None,
            "reason": f"Sensor status is '{current_reading.temp_status}', not measured",
        }

    # Data freshness check
    if current_reading.ts:
        ts = current_reading.ts if current_reading.ts.tzinfo else current_reading.ts.replace(tzinfo=timezone.utc)
        age_sec = (datetime.now(timezone.utc) - ts).total_seconds()
        if age_sec > 300:
            return {
                "confidence_level": "low",
                "trust": "low",
                "calibrated": False,
                "sample_count": 0,
                "mean_error_c": None,
                "reason": "Telemetry is stale (> 5 minutes old)",
            }

    verified_errors = [
        v["error_c"] for v in verification_history
        if v.get("verified") is True and v.get("error_c") is not None
    ]

    if len(verified_errors) < 5:
        return {
            "confidence_level": "low",
            "trust": "low",
            "calibrated": False,
            "sample_count": len(verified_errors),
            "mean_error_c": None if not verified_errors else round(float(sum(verified_errors) / len(verified_errors)), 2),
            "reason": "Insufficient verified historical forecasts to calibrate confidence",
        }

    mean_err = float(sum(verified_errors) / len(verified_errors))

    if mean_err <= 1.5 and (mae is None or mae <= 2.0):
        confidence_level = "high"
        trust = "high"
    elif mean_err <= 3.5:
        confidence_level = "medium"
        trust = "medium"
    else:
        confidence_level = "low"
        trust = "low"

    return {
        "confidence_level": confidence_level,
        "trust": trust,
        "calibrated": True,
        "sample_count": len(verified_errors),
        "mean_error_c": round(mean_err, 2),
        "reason": f"Calibrated against {len(verified_errors)} verified historical forecasts",
    }

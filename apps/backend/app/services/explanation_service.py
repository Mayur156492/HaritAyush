"""Explainable warning causes service for HaritAyush backend."""

from __future__ import annotations

from typing import List, Dict, Any, Optional

from app.models import Reading


def rank_causes(
    reading: Reading,
    forecast: dict,
    limit_c: float,
    trust: str,
    recent_readings: Optional[List[Reading]] = None,
) -> List[Dict[str, Any]]:
    """Rank explainable causes of a temperature warning in plain language.

    Per PRD §9:
    - Every cause must be supported by actual observed data or model evidence.
    - No fabricated telemetry statements (e.g. no fake 'rose from 40% to 95% in 3 min').
    - Do not claim a trend unless multiple timestamped observations support it.
    - Remove duplicate or overlapping temperature-proximity explanations.
    - Preserves honest uncertainty and plain language.
    """
    causes: List[Dict[str, Any]] = []

    cpu_pct = reading.cpu_pct
    temp_c = reading.cpu_temp_c

    # 1. Historical CPU Trend Analysis (only if actual past readings exist)
    if recent_readings and len(recent_readings) >= 2 and cpu_pct is not None:
        # Sort recent readings chronologically
        sorted_recent = sorted(
            [r for r in recent_readings if r.cpu_pct is not None and r.ts is not None],
            key=lambda r: r.ts,
        )
        if len(sorted_recent) >= 2:
            earliest = sorted_recent[0]
            latest = sorted_recent[-1]
            dt_min = (latest.ts - earliest.ts).total_seconds() / 60.0
            if dt_min >= 1.0:
                cpu_diff = latest.cpu_pct - earliest.cpu_pct
                if cpu_diff >= 20.0:
                    causes.append({
                        "cause": f"Observed CPU utilisation increased from {earliest.cpu_pct:.1f}% to {latest.cpu_pct:.1f}% over {dt_min:.1f} min",
                        "weight": 0.5,
                    })

    # 2. Current CPU load evidence
    if cpu_pct is not None:
        if cpu_pct >= 90.0:
            causes.append({
                "cause": f"Critical CPU workload detected ({cpu_pct:.1f}% utilisation)",
                "weight": 0.45,
            })
        elif cpu_pct >= 75.0:
            causes.append({
                "cause": f"Elevated CPU utilisation active ({cpu_pct:.1f}%)",
                "weight": 0.35,
            })

    # 3. Current Temperature Proximity (single consolidated check, no duplicate explanations)
    if temp_c is not None and limit_c is not None and limit_c > 0:
        diff_to_limit = limit_c - temp_c
        if diff_to_limit <= 0:
            causes.append({
                "cause": f"Observed temperature ({temp_c:.1f}°C) has reached danger limit ({limit_c:.1f}°C)",
                "weight": 0.6,
            })
        elif diff_to_limit <= 5.0:
            causes.append({
                "cause": f"Observed temperature ({temp_c:.1f}°C) is within 5°C of danger limit ({limit_c:.1f}°C)",
                "weight": 0.5,
            })
        elif diff_to_limit <= 12.0:
            causes.append({
                "cause": f"Observed temperature ({temp_c:.1f}°C) is approaching threshold ({limit_c:.1f}°C)",
                "weight": 0.3,
            })

    # 4. Forecast Trajectory Evidence
    hi_15 = forecast.get("15", {}).get("hi") if isinstance(forecast, dict) else None
    if hi_15 is not None and limit_c is not None:
        if hi_15 >= limit_c:
            causes.append({
                "cause": f"15-minute upper forecast ({hi_15:.1f}°C) projects breach of limit ({limit_c:.1f}°C)",
                "weight": 0.4,
            })

    # 5. Telemetry Quality / Trust context
    if trust == "low":
        causes.append({
            "cause": "Forecast uncertainty is elevated due to limited or estimated sensor telemetry",
            "weight": 0.2,
        })

    # Fallback if no specific causes
    if not causes:
        causes.append({
            "cause": "Thermal parameters operating within normal margins",
            "weight": 0.1,
        })

    # Deduplicate causes by text
    seen_text = set()
    unique_causes = []
    for c in causes:
        if c["cause"] not in seen_text:
            seen_text.add(c["cause"])
            unique_causes.append(c)

    # Sort descending by weight
    unique_causes.sort(key=lambda c: c["weight"], reverse=True)
    return unique_causes


def build_why_payload(
    reading: Reading,
    forecast: dict,
    limit_c: float,
    trust: str,
    recent_readings: Optional[List[Reading]] = None,
) -> List[Dict[str, Any]]:
    """Build the 'why' field for the forecast contract response."""
    return rank_causes(reading, forecast, limit_c, trust, recent_readings)

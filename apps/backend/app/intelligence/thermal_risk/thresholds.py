"""Thermal risk thresholds for HaritAyush backend.

Holds boundaries between thermal risk levels per PRD §4, §6 (B5), and §8:
- Default danger limit: 85.0°C (configurable provisional demo default)
- Elevated margin: 5.0°C (risk is Elevated when upper forecast reaches limit - 5°C)

Thresholds must be justified by vendor guidance or device capability data.
They must not be arbitrary invented numbers, and may differ per device class.
"""

from __future__ import annotations

DEFAULT_DANGER_LIMIT_C: float = 85.0
ELEVATED_MARGIN_C: float = 5.0


def get_risk_thresholds(site_id: str | None = None) -> dict[str, float]:
    """Return the threshold set applicable to a device.

    Per PRD §8: Configurable danger limit (limit_c) with provisional demo default 85°C.
    """
    return {
        "limit_c": DEFAULT_DANGER_LIMIT_C,
        "elevated_margin_c": ELEVATED_MARGIN_C,
    }

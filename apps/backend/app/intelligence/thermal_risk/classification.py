"""Thermal risk classification for HaritAyush backend.

Maps an assessed thermal condition onto a risk category per PRD §4, §6 (B5), and §8:
- High: upper forecast band reaches limit_c within 15 minutes.
- Elevated: upper forecast band reaches limit_c - 5°C within 15 minutes.
- Normal: neither condition is met.

A device whose thermal condition cannot be measured gets Normal with low trust;
it must not be silently classified as safe. Classification must not imply that
a temperature reading alone proves device health or lifespan.
"""

from __future__ import annotations


def classify_risk(
    hi_temp: float | None,
    limit_c: float = 85.0,
    current_temp: float | None = None,
) -> str:
    """Map an assessed condition onto a risk category: High, Elevated, or Normal."""
    if current_temp is not None and current_temp >= limit_c:
        return "High"

    if hi_temp is None:
        return "Normal"

    if hi_temp >= limit_c:
        return "High"
    elif hi_temp >= (limit_c - 5.0):
        return "Elevated"
    else:
        return "Normal"

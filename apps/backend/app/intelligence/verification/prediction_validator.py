"""Verification of forecasts against observed hardware temperatures.

Scaffold placeholder (backend owner). This module will compare a stored
forecast with the temperature actually observed at the forecast target time,
so that the platform's forecasts can be judged against reality rather than
assumed to be correct.

Rules carried by this placeholder:

- Verification requires a real observation for the target timestamp. If the
  device did not report a reading, the forecast is recorded as unverified, not
  as correct.
- Observed values are never interpolated or synthesised to make a comparison
  pass.
- Comparisons must account for the sampling interval and for sensor
  unavailability on devices without temperature sensors.

No verification logic, tolerance or scoring is implemented yet.
"""

from __future__ import annotations


def verify_prediction(*args: object, **kwargs: object) -> object:
    """Compare one forecast against the observation at its target time.

    Placeholder. Matching rules, handling of missing observations and the
    output representation await the forecast contract.

    Raises:
        NotImplementedError: Always, in the current scaffold.
    """
    raise NotImplementedError(
        "Prediction verification is not implemented in the repository scaffold."
    )

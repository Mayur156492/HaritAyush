"""Confidence and uncertainty for temperature forecasts.

Scaffold placeholder (backend owner). This module will express how much trust
a forecast deserves, based on the model's measured behaviour over verified
forecasts and on the completeness of the telemetry it was given.

Rules carried by this placeholder:

- Confidence must be derived from recorded verification history and data
  completeness, never asserted as a fixed or invented number.
- A forecast produced from missing or sparse telemetry must be marked as
  low-confidence rather than silently presented as reliable.
- Uncertainty must be visible to the risk assessment and the dashboard; the
  UI must not imply more certainty than the data supports.

No confidence calculation exists in the scaffold.
"""

from __future__ import annotations


def estimate_confidence(*args: object, **kwargs: object) -> object:
    """Estimate the reliability of a temperature forecast.

    Placeholder. Inputs, calibration approach and output representation
    await the forecast and verification contracts.

    Raises:
        NotImplementedError: Always, in the current scaffold.
    """
    raise NotImplementedError(
        "Forecast confidence estimation is not implemented in the repository scaffold."
    )

"""Forecast model orchestration.

Scaffold placeholder (backend owner). This module will select and drive a
forecasting model for a requested horizon and return a forecast in the shape
required by the forecast contract.

Intended horizons are 5 minutes and 15 minutes ahead, provided that the
eventual telemetry frequency and available history support them. Horizon
support must be reported honestly: a model must not appear to serve a horizon
that its training data cannot resolve.

This module must keep the four approaches interchangeable and comparable:

- persistence baseline
- SARIMA
- SARIMAX
- XGBoost

No dispatcher, model registry, caching, training or prediction is implemented
in the scaffold, and no forecast values exist anywhere in this repository.
"""

from __future__ import annotations


def forecast_temperature(*args: object, **kwargs: object) -> object:
    """Produce a temperature forecast for a requested horizon.

    Placeholder. Model selection policy, horizon definitions and the returned
    representation await the approved forecast contract.

    Raises:
        NotImplementedError: Always, in the current scaffold.
    """
    raise NotImplementedError(
        "Forecast orchestration is not implemented in the repository scaffold."
    )

"""Forecast model evaluation and comparison.

Scaffold placeholder (backend owner). This module will compare the persistence
baseline, SARIMA, SARIMAX and XGBoost forecasts.

Non-negotiable evaluation rules:

- Every model is evaluated over identical chronological test periods. Random
  splits, shuffled folds and any other scheme that mixes past and future are
  not acceptable.
- No temporal data leakage: a forecast may use only data available at its
  origin, and test data may not influence fitting or feature scaling.
- MAE and RMSE are the supported error metrics. Additional metrics may be
  added only with justification.
- Reported results must come from real recorded telemetry. No metric values
  are generated or claimed by this scaffold.

No splitting, metric computation or reporting is implemented yet.
"""

from __future__ import annotations


def evaluate_forecasts(*args: object, **kwargs: object) -> object:
    """Compare model forecasts on identical chronological test periods.

    Placeholder. Metric implementation, error handling for unavailable sensor
    readings and the comparison output format are not yet defined.

    Raises:
        NotImplementedError: Always, in the current scaffold.
    """
    raise NotImplementedError(
        "Forecast evaluation is not implemented in the repository scaffold."
    )

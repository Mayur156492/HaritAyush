"""XGBoost temperature forecasting model.

Scaffold placeholder (backend owner). XGBoost provides the nonlinear
multivariable approach: it forecasts temperature from engineered historical
telemetry features rather than from a univariate series alone.

Library: ``xgboost``. The library is declared in ``pyproject.toml`` but is not
imported at module import time, so the scaffold remains importable without the
scientific stack.

Rules carried by this placeholder:

- Features come from ``feature_engineering`` and must be free of temporal
  leakage; no future observations may be used as inputs.
- No hyperparameters, feature lists or training runs are defined, and no
  accuracy figure is claimed.
- Missing telemetry is represented as unavailable, not fabricated.
"""

from __future__ import annotations


class XGBoostTemperatureModel:
    """Nonlinear multivariable temperature forecaster (not implemented)."""

    def fit(self, *args: object, **kwargs: object) -> "XGBoostTemperatureModel":
        """Placeholder for training the model on engineered features.

        Raises:
            NotImplementedError: Always, in the current scaffold.
        """
        raise NotImplementedError(
            "XGBoost forecasting is not implemented in the repository scaffold."
        )

    def forecast(self, *args: object, **kwargs: object) -> object:
        """Placeholder for forecasting temperatures from engineered features.

        Raises:
            NotImplementedError: Always, in the current scaffold.
        """
        raise NotImplementedError(
            "XGBoost forecasting is not implemented in the repository scaffold."
        )

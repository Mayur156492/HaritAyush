"""SARIMA temperature forecasting model.

Scaffold placeholder (backend owner). SARIMA is the univariate approach: it
forecasts temperature from the historical temperature series alone, using
trend and seasonal terms only where the recorded data actually justifies them.

Library: ``statsmodels``. The library is declared in ``pyproject.toml`` but is
deliberately not imported at module import time, so that the scaffold and the
health check do not depend on the scientific stack being installed.

No order selection, fitting, forecasting or evaluation is implemented, and no
seasonal period or accuracy figure is assumed.
"""

from __future__ import annotations


class SarimaTemperatureModel:
    """Univariate SARIMA temperature forecaster (not implemented)."""

    def fit(self, *args: object, **kwargs: object) -> "SarimaTemperatureModel":
        """Placeholder for fitting the SARIMA model on temperature history.

        Raises:
            NotImplementedError: Always, in the current scaffold.
        """
        raise NotImplementedError(
            "SARIMA forecasting is not implemented in the repository scaffold."
        )

    def forecast(self, *args: object, **kwargs: object) -> object:
        """Placeholder for forecasting future temperatures.

        Raises:
            NotImplementedError: Always, in the current scaffold.
        """
        raise NotImplementedError(
            "SARIMA forecasting is not implemented in the repository scaffold."
        )

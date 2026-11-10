"""SARIMAX temperature forecasting model.

Scaffold placeholder (backend owner). SARIMAX forecasts temperature from the
historical temperature series together with relevant external variables such
as CPU utilisation, GPU utilisation, power consumption and workload intensity.

Library: ``statsmodels``. The library is declared in ``pyproject.toml`` but is
not imported at module import time.

Open design question that this module must not hide: future exogenous values
are not automatically known. Before this model can produce a genuine forecast,
each external variable must be obtained in one of three documented ways:

1. Forecast separately by its own model, with that forecast's uncertainty
   carried into the temperature forecast.
2. Supplied from a known schedule (for example, a planned workload schedule
   that is authoritative for the forecast horizon).
3. Handled by a documented fallback (for example, holding the last observed
   value), which must be stated as an assumption wherever the forecast is
   presented.

No exogenous variable set, no fallback policy and no fitting logic is
implemented or assumed in the scaffold.
"""

from __future__ import annotations


class SarimaxTemperatureModel:
    """SARIMAX temperature forecaster with external regressors (not implemented)."""

    def fit(self, *args: object, **kwargs: object) -> "SarimaxTemperatureModel":
        """Placeholder for fitting the model on temperature and exogenous history.

        Raises:
            NotImplementedError: Always, in the current scaffold.
        """
        raise NotImplementedError(
            "SARIMAX forecasting is not implemented in the repository scaffold."
        )

    def forecast(self, *args: object, **kwargs: object) -> object:
        """Placeholder for forecasting temperatures over a horizon.

        Future exogenous inputs must be supplied by a documented mechanism;
        this placeholder does not define or assume one.

        Raises:
            NotImplementedError: Always, in the current scaffold.
        """
        raise NotImplementedError(
            "SARIMAX forecasting is not implemented in the repository scaffold."
        )

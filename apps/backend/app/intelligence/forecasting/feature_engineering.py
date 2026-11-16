"""Feature preparation for temperature forecasting.

Scaffold placeholder (backend owner). This module will derive the features
used by the SARIMAX and XGBoost models, and the covariate series supplied to
SARIMAX.

Scope rules established by the repository specification:

- Features must be computed only from information available at the forecast
  origin, so that chronological evaluation is free of temporal leakage.
- Candidate drivers include CPU utilisation, GPU utilisation, power
  consumption and workload intensity, subject to what the local agent can
  actually observe on a given device.
- Missing drivers are represented as unavailable, not invented.
- Lags, rolling statistics and calendar features are not yet defined; the
  eventual design must be justified by the recorded data frequency and
  history length.

Nothing is implemented yet.
"""

from __future__ import annotations


def build_features(*args: object, **kwargs: object) -> object:
    """Prepare forecasting features from historical telemetry.

    Placeholder. Feature definitions, windows and lag structure will be
    specified together with the approved telemetry contract.

    Raises:
        NotImplementedError: Always, in the current scaffold.
    """
    raise NotImplementedError(
        "Forecast feature engineering is not implemented in the repository scaffold."
    )

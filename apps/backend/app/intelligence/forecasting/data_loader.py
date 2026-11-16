"""Historical telemetry loading for temperature forecasting.

Scaffold placeholder (backend owner). This module will load the historical
hardware telemetry used to fit and evaluate temperature forecasts.

Scope rules established by the repository specification:

- Only recorded telemetry may be used. No training data may be invented.
- Sources are the backend ``data/raw``, ``data/processed`` and ``data/sample``
  directories and telemetry persisted from enrolled devices.
- A reading that a device cannot expose must be represented as unavailable.
  It must never be replaced with a fabricated value or silently imputed.
- Loading must preserve chronological order so that models can be evaluated
  on identical chronological test periods.

Nothing is implemented yet. No data files, columns or schemas have been
defined; those follow the telemetry contract and backend architecture work.
"""

from __future__ import annotations


def load_temperature_history(*args: object, **kwargs: object) -> object:
    """Load historical temperature observations for forecasting.

    Placeholder. The concrete signature, accepted sources and returned
    representation will be agreed once the telemetry contract is approved.

    Raises:
        NotImplementedError: Always, in the current scaffold.
    """
    raise NotImplementedError(
        "Telemetry loading is not implemented in the repository scaffold."
    )

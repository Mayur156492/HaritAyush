"""Energy consumption estimation.

Scaffold placeholder (backend owner). This module will estimate the energy a
device or workload consumes over a period, for comparison in the placement
decision.

Rules carried by this placeholder:

- Energy values must be labelled as measured or estimated. A reading from a
  platform power counter is not the same as a model-derived estimate, and the
  two must never be presented as interchangeable.
- Where power cannot be observed, the estimate's basis and assumptions must be
  recorded with the value.
- No default power figures are baked into the scaffold, because they would
  become invented measurements.

No estimation method or value is implemented.
"""

from __future__ import annotations


def estimate_energy(*args: object, **kwargs: object) -> object:
    """Estimate energy consumption for a device or workload over a period.

    Placeholder. Inputs, method and the measured/estimated labelling await the
    telemetry contract and the sustainability design.

    Raises:
        NotImplementedError: Always, in the current scaffold.
    """
    raise NotImplementedError(
        "Energy estimation is not implemented in the repository scaffold."
    )

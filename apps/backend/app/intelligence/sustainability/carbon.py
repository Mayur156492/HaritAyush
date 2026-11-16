"""Carbon impact estimation.

Scaffold placeholder (backend owner). This module will convert energy figures
into carbon estimates using an explicit, documented grid emission factor.

Rules carried by this placeholder:

- Carbon values derived from estimated energy must be labelled estimated, and
  values derived from measured energy must say so; the chain of assumptions
  must be traceable.
- The grid emission factor is an external assumption. Its source, region and
  date must be recorded with every result, and it must not be presented as a
  measurement from this platform.
- No emission factor, region or value is hard-coded in the scaffold.

No carbon calculation is implemented.
"""

from __future__ import annotations


def estimate_carbon(*args: object, **kwargs: object) -> object:
    """Estimate carbon impact from energy consumption.

    Placeholder. Emission-factor sourcing, labelling and output representation
    await the sustainability design.

    Raises:
        NotImplementedError: Always, in the current scaffold.
    """
    raise NotImplementedError(
        "Carbon estimation is not implemented in the repository scaffold."
    )

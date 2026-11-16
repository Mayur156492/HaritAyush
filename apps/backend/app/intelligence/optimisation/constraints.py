"""Placement constraints.

Scaffold placeholder (backend owner). This module will express the conditions a
placement must satisfy before it can be recommended.

Constraints to encode once the contracts are approved include, at minimum:

- The device is enrolled and reports a live, trusted telemetry stream.
- The workload is authorised for the target device.
- Forecast thermal headroom is sufficient for the workload's duration, with
  uncertainty taken into account.
- The required hardware capability is genuinely present, as discovered, not as
  assumed from the device model.
- Firmware thermal protection and the agent's local safety rules are never
  bypassed.

No constraint is implemented or parameterised in the scaffold.
"""

from __future__ import annotations


def evaluate_constraints(*args: object, **kwargs: object) -> object:
    """Check whether a candidate placement satisfies all constraints.

    Placeholder. Constraint definitions and violation reporting await the
    workload and command contracts.

    Raises:
        NotImplementedError: Always, in the current scaffold.
    """
    raise NotImplementedError(
        "Placement constraints are not implemented in the repository scaffold."
    )

"""Placement scoring.

Scaffold placeholder (backend owner). This module will score candidate devices
for a workload so that placement recommendations are explainable.

Rules carried by this placeholder:

- Every score component must trace back to recorded telemetry, a documented
  device capability or an approved constraint. Weights must be justified, not
  invented.
- Scores presented to users must show their inputs, so a recommendation can be
  reviewed rather than trusted blindly.
- Missing inputs reduce confidence in a score; they are not silently filled
  with optimistic defaults.

No scoring factors, weights or formulas are defined in the scaffold.
"""

from __future__ import annotations


def score_candidates(*args: object, **kwargs: object) -> object:
    """Score candidate devices for a workload placement decision.

    Placeholder. Factors, weights and the explanation format await the
    placement design.

    Raises:
        NotImplementedError: Always, in the current scaffold.
    """
    raise NotImplementedError(
        "Placement scoring is not implemented in the repository scaffold."
    )

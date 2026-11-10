"""Sustainability reporting.

Scaffold placeholder (backend owner). This module will assemble energy, carbon
and water impact information for the dashboard and for exported reports.

Rules carried by this placeholder:

- Every reported figure carries its provenance: measured or estimated, the
  period covered, and the assumptions behind it.
- Totals must not mix measured and estimated components without showing the
  split.
- Reports must not claim device lifespan extension based solely on a
  temperature reduction. Lower temperature is not evidence of longer hardware
  life, and this platform does not assert it.
- Water impact requires the same discipline: a documented model or an explicit
  "not available", never a fabricated number.

No report structure, aggregation or export is implemented.
"""

from __future__ import annotations


def build_sustainability_report(*args: object, **kwargs: object) -> object:
    """Assemble a sustainability report for a period.

    Placeholder. Figure provenance, aggregation and export format await the
    sustainability design.

    Raises:
        NotImplementedError: Always, in the current scaffold.
    """
    raise NotImplementedError(
        "Sustainability reporting is not implemented in the repository scaffold."
    )

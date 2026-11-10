"""Thermal-aware workload placement.

Scaffold placeholder (backend owner). This module will recommend where an
authorised workload should run, using forecast thermal risk, device capability
and the declared constraints.

Rules carried by this placeholder:

- Only enrolled devices are candidates, and only authorised workloads are
  placed. There is no discovery-and-adopt behaviour.
- Placement is a recommendation that enters the approval stage of the
  operational cycle; nothing in this module executes a command directly.
- The local agent's own safety validation remains authoritative and
  independent of backend connectivity. A placement that the agent rejects is
  not forced through.
- A device with unknown thermal capability must not be treated as having
  spare thermal headroom.

No placement algorithm is implemented and no capability claims are made.
"""

from __future__ import annotations


def recommend_placement(*args: object, **kwargs: object) -> object:
    """Recommend a device for an authorised workload.

    Placeholder. Candidate scoring, constraint handling and the recommendation
    output await the workload contract and the placement design.

    Raises:
        NotImplementedError: Always, in the current scaffold.
    """
    raise NotImplementedError(
        "Workload placement is not implemented in the repository scaffold."
    )

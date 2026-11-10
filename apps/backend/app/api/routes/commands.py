"""GET /commands/pending — Return pending commands for the Windows agent.

Supports approved cpu_cap commands and presenter commands start_job / stop_job.
Per PRD section 5.E:
- Do not deliver pending recommendations as approved commands.
- Only deliver a cpu_cap command after approval.
- Preserve action identifiers and recommendation traceability.
- Prevent dismissed or already-consumed commands from being delivered as new commands.
- Represent command status explicitly.
- Avoid duplicate command execution caused by repeated polling.
- Do not implement Windows process control in the backend.
"""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Query

from ...schemas import CommandPendingResponse, CommandItem
from ...models import Command
from ...services.command_service import get_pending_commands


router = APIRouter(tags=["commands"])


@router.get(
    "/pending",
    response_model=CommandPendingResponse,
    summary="Get pending commands for agent",
    description="Return pending commands that may be delivered to the Windows "
    "agent enclosed in a 'commands' envelope. Handed-out commands are atomically "
    "marked delivered so subsequent polls do not return duplicates.",
)
def get_pending_commands_endpoint(
    site_id: str = Query("laptop-01", description="Site/device identifier"),
):
    """Get pending commands for the Windows agent in envelope format."""
    commands = get_pending_commands(site_id=site_id, mark_as_delivered=True)
    items = []
    for c in commands:
        issued_at_str = c.created_at.isoformat() if hasattr(c.created_at, "isoformat") else str(c.created_at)
        approved_at_str = (
            c.approved_at.isoformat()
            if hasattr(getattr(c, "approved_at", None), "isoformat")
            else (str(c.approved_at) if getattr(c, "approved_at", None) else None)
        )
        items.append(
            CommandItem(
                id=c.id,
                type=c.command_type,
                issued_at=issued_at_str,
                status=c.status,
                action_id=c.action_id,
                cap_pct=getattr(c, "cap_pct", None),
                approved_by=getattr(c, "approved_by", None),
                approved_at=approved_at_str,
            )
        )
    return CommandPendingResponse(commands=items)

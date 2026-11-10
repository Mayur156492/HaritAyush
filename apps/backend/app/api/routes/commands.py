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

from ...schemas import CommandPending
from ...models import Command
from ...services.command_service import get_pending_commands


router = APIRouter(tags=["commands"])


@router.get(
    "/pending",
    response_model=List[CommandPending],
    summary="Get pending commands for agent",
    description="Return pending commands that may be delivered to the Windows "
    "agent.  Only approved cpu_cap commands are delivered.  Presenter commands "
    "start_job and stop_job are also supported.  A cpu_cap command is only "
    "delivered after the associated recommendation has been approved by the "
    "operator.",
)
async def get_pending_commands_endpoint(
    site_id: str = Query("laptop-01", description="Site/device identifier"),
):
    """Get pending commands for the Windows agent."""
    commands = get_pending_commands(site_id=site_id)
    return [
        CommandPending(
            action_id=c.action_id,
            command_type=c.command_type,
            cap_pct=getattr(c, "cap_pct", None),
            status=c.status,
            created_at=c.created_at.isoformat() if hasattr(c.created_at, "isoformat") else str(c.created_at),
        )
        for c in commands
    ]
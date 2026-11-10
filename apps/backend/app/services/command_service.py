"""Command service for HaritAyush backend — pending commands for the Windows agent."""

from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import select

from app.models import Command, Recommendation
from app.database import session_factory


def get_pending_commands(site_id: str) -> list[Command]:
    """Return pending commands for a device that may be delivered to the agent.

    Per PRD §5.E:
    - Only deliver approved cpu_cap commands (not undelivered pending recommendations).
    - Only deliver a cpu_cap command after approval.
    - Preserve action identifiers and recommendation traceability.
    - Prevent dismissed or already-consumed commands from being delivered as new commands.
    - Represent command status explicitly.
    - Avoid duplicate command execution caused by repeated polling.
    - Do not implement Windows process control in the backend.
    """
    with session_factory() as session:
        stmt = (
            select(Command)
            .where(
                Command.site_id == site_id,
                Command.status == "pending",
            )
            .order_by(Command.created_at.asc(), Command.id.asc())
        )
        result = session.execute(stmt)
        commands = list(result.scalars().all())

        # For cpu_cap commands, resolve cap_pct from the associated Recommendation
        for cmd in commands:
            if cmd.command_type == "cpu_cap" and cmd.action_id:
                rec = session.execute(
                    select(Recommendation).where(
                        Recommendation.site_id == site_id,
                        Recommendation.action_id == cmd.action_id,
                    ).order_by(Recommendation.created_at.desc(), Recommendation.id.desc())
                ).scalars().first()
                cmd.cap_pct = rec.cap_pct if rec else None
            else:
                cmd.cap_pct = None

        return commands


def create_pending_command(
    site_id: str,
    command_type: str,
    action_id: str,
    cap_pct: int | None = None,
) -> Command:
    """Create a pending command for the Windows agent."""
    from app.models import Command as _Command

    cmd = _Command(
        site_id=site_id,
        action_id=action_id,
        command_type=command_type,
        status="pending",
        created_at=datetime.now(timezone.utc),
    )

    with session_factory() as session:
        session.add(cmd)
        session.commit()
        session.refresh(cmd)
        cmd.cap_pct = cap_pct

    return cmd


def mark_command_delivered(cmd_id: int) -> bool:
    """Mark a command as delivered after the agent executes it."""
    from app.models import Command as _Command

    with session_factory() as session:
        cmd = session.get(_Command, cmd_id)
        if cmd is None:
            return False
        cmd.status = "delivered"
        cmd.delivered_at = datetime.now(timezone.utc)
        session.commit()
        return True


def mark_command_consumed(cmd_id: int) -> bool:
    """Mark a command as consumed after the agent processes it."""
    from app.models import Command as _Command

    with session_factory() as session:
        cmd = session.get(_Command, cmd_id)
        if cmd is None:
            return False
        cmd.status = "consumed"
        session.commit()
        return True
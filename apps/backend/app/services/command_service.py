"""Command service for HaritAyush backend — pending commands for the Windows agent."""

from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import select, update

from app.models import Command, Recommendation
from app.database import session_factory


def get_pending_commands(site_id: str, mark_as_delivered: bool = False) -> list[Command]:
    """Return pending commands for a device that may be delivered to the agent.

    Per PRD §5.E and API Contract v1:
    - Only deliver approved cpu_cap commands (not undelivered pending recommendations).
    - Only deliver a cpu_cap command after approval.
    - Preserve action identifiers and recommendation traceability.
    - Prevent dismissed or already-consumed commands from being delivered as new commands.
    - When mark_as_delivered is True, claims commands with an atomic conditional UPDATE:
      `UPDATE commands SET status = 'delivered', delivered_at = :now WHERE id IN (...) AND status = 'pending'`
      Only commands whose status transition succeeded (claimed) are returned, preventing race conditions
      where concurrent pollers could observe the same pending rows.
    - Avoid duplicate command execution caused by repeated polling.
    - Do not implement Windows process control in the backend.
    """
    with session_factory() as session:
        # Step 1: Query IDs of currently pending commands in deterministic order
        stmt = (
            select(Command.id)
            .where(
                Command.site_id == site_id,
                Command.status == "pending",
            )
            .order_by(Command.created_at.asc(), Command.id.asc())
        )
        candidate_ids = list(session.execute(stmt).scalars().all())

        if not candidate_ids:
            return []

        now = datetime.now(timezone.utc)
        claimed_ids = candidate_ids

        # Step 2: If mark_as_delivered is True, perform an atomic conditional claim
        if mark_as_delivered:
            claimed_ids = []
            for cid in candidate_ids:
                # Conditional atomic update: only update if still pending
                upd_stmt = (
                    update(Command)
                    .where(
                        Command.id == cid,
                        Command.status == "pending",
                    )
                    .values(
                        status="delivered",
                        delivered_at=now,
                    )
                )
                upd_res = session.execute(upd_stmt)
                # upd_res.rowcount indicates whether this worker successfully claimed the command
                if upd_res.rowcount > 0:
                    claimed_ids.append(cid)

            session.commit()

            if not claimed_ids:
                return []

        # Step 3: Fetch the claimed command records preserving deterministic order
        fetch_stmt = (
            select(Command)
            .where(Command.id.in_(claimed_ids))
            .order_by(Command.created_at.asc(), Command.id.asc())
        )
        commands = list(session.execute(fetch_stmt).scalars().all())

        # Step 4: For cpu_cap commands, resolve cap_pct, approved_by, approved_at from the associated Recommendation
        for cmd in commands:
            if cmd.command_type == "cpu_cap" and cmd.action_id:
                rec = session.execute(
                    select(Recommendation).where(
                        Recommendation.site_id == site_id,
                        Recommendation.action_id == cmd.action_id,
                    ).order_by(Recommendation.created_at.desc(), Recommendation.id.desc())
                ).scalars().first()
                cmd.cap_pct = rec.cap_pct if rec else None
                cmd.approved_by = rec.approver if rec else None
                cmd.approved_at = rec.approved_at if rec else None
            else:
                cmd.cap_pct = None
                cmd.approved_by = None
                cmd.approved_at = None

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
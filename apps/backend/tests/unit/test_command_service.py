"""Unit tests for pending commands service."""

from app.models import Command, Recommendation
from app.services.action_service import create_recommendation, approve_recommendation
from app.services.command_service import (
    get_pending_commands,
    create_pending_command,
    mark_command_delivered,
    mark_command_consumed,
)
from app.database import session_factory


def test_get_pending_commands_empty():
    """Verify empty list when no commands exist."""
    cmds = get_pending_commands("laptop-01")
    assert cmds == []


def test_get_pending_commands_with_cap_pct_resolution():
    """Verify that approved cpu_cap command has cap_pct resolved from Recommendation."""
    rec = create_recommendation(
        site_id="laptop-01",
        action_type="cpu_cap",
        cap_pct=60,
        action_id="a-cmd-test-1",
    )
    approve_recommendation(rec.id, operator="op1")

    pending = get_pending_commands("laptop-01")
    assert len(pending) == 1
    cmd = pending[0]
    assert cmd.action_id == "a-cmd-test-1"
    assert cmd.command_type == "cpu_cap"
    assert cmd.status == "pending"
    assert cmd.cap_pct == 60


def test_mark_command_delivered_and_consumed():
    """Verify command status transitions from pending -> delivered -> consumed."""
    rec = create_recommendation(
        site_id="laptop-01",
        action_type="cpu_cap",
        cap_pct=50,
        action_id="a-cmd-lifecycle",
    )
    approve_recommendation(rec.id)

    pending = get_pending_commands("laptop-01")
    assert len(pending) == 1
    cmd_id = pending[0].id

    # Mark delivered
    delivered = mark_command_delivered(cmd_id)
    assert delivered is True

    # No longer pending
    pending_after_deliver = get_pending_commands("laptop-01")
    assert pending_after_deliver == []

    # Mark consumed
    consumed = mark_command_consumed(cmd_id)
    assert consumed is True

    with session_factory() as session:
        c = session.get(Command, cmd_id)
        assert c.status == "consumed"


def test_presenter_commands_start_and_stop_job():
    """Verify that presenter commands like start_job and stop_job can be created and queried."""
    cmd1 = create_pending_command(
        site_id="laptop-01",
        command_type="start_job",
        action_id="presenter-start-1",
    )
    assert cmd1.id is not None
    assert cmd1.command_type == "start_job"

    pending = get_pending_commands("laptop-01")
    assert len(pending) == 1
    assert pending[0].command_type == "start_job"
    assert pending[0].cap_pct is None


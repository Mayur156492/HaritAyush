"""Focused unit tests for command delivery API Contract v1 and lifecycle."""

import pytest
from app.models import Command, Recommendation
from app.services.action_service import (
    create_recommendation,
    approve_recommendation,
    dismiss_recommendation,
)
from app.services.command_service import (
    get_pending_commands,
    create_pending_command,
    mark_command_delivered,
    mark_command_consumed,
)
from app.api.routes.commands import get_pending_commands_endpoint


def test_command_delivery_envelope_and_fields():
    """Verify GET /commands/pending endpoint returns {'commands': [...]} with all required fields."""
    rec = create_recommendation(
        site_id="laptop-01",
        action_type="cpu_cap",
        cap_pct=45,
        action_id="act-envelope-1",
    )
    approve_recommendation(rec.id, operator="admin-op", reason="Thermal limit predicted")

    # Call synchronous endpoint function directly
    response = get_pending_commands_endpoint(site_id="laptop-01")
    data = response.model_dump()

    # 1. Envelope check
    assert "commands" in data
    assert isinstance(data["commands"], list)
    assert len(data["commands"]) == 1

    cmd = data["commands"][0]
    # 2. Required fields
    assert cmd["id"] is not None
    assert cmd["type"] == "cpu_cap"
    assert cmd["issued_at"] is not None
    assert cmd["status"] == "delivered"  # Handed out and marked delivered

    # 3. CPU-cap specific fields
    assert cmd["cap_pct"] == 45
    assert cmd["action_id"] == "act-envelope-1"
    assert cmd["approved_by"] == "admin-op"
    assert cmd["approved_at"] is not None


def test_first_poll_delivers_and_second_poll_is_empty():
    """First poll returns eligible command and marks it delivered; second poll returns empty list."""
    rec = create_recommendation(
        site_id="laptop-01",
        action_type="cpu_cap",
        cap_pct=60,
        action_id="act-poll-once",
    )
    approve_recommendation(rec.id, operator="op-user")

    # First poll
    poll1 = get_pending_commands_endpoint(site_id="laptop-01")
    assert len(poll1.commands) == 1
    assert poll1.commands[0].action_id == "act-poll-once"

    # Second poll immediately following
    poll2 = get_pending_commands_endpoint(site_id="laptop-01")
    assert len(poll2.commands) == 0


def test_dismissed_recommendation_never_produces_commands():
    """Dismissing a recommendation must never produce deliverable commands."""
    rec = create_recommendation(
        site_id="laptop-01",
        action_type="cpu_cap",
        cap_pct=50,
        action_id="act-dismiss-safe",
    )
    dismiss_recommendation(rec.id, operator="op-dismiss", reason="False alarm")

    poll = get_pending_commands_endpoint(site_id="laptop-01")
    assert len(poll.commands) == 0


def test_unapproved_recommendation_never_delivered():
    """Pending recommendation without approval cannot produce deliverable commands."""
    rec = create_recommendation(
        site_id="laptop-01",
        action_type="cpu_cap",
        cap_pct=50,
        action_id="act-pending-safe",
    )
    # No approve called

    poll = get_pending_commands_endpoint(site_id="laptop-01")
    assert len(poll.commands) == 0


def test_command_service_delivered_to_consumed_lifecycle():
    """Delivered command is not marked consumed until explicit consumption."""
    rec = create_recommendation(
        site_id="laptop-01",
        action_type="cpu_cap",
        cap_pct=50,
        action_id="act-consume-test",
    )
    approve_recommendation(rec.id)

    # Hand out with mark_as_delivered=True
    cmds = get_pending_commands("laptop-01", mark_as_delivered=True)
    assert len(cmds) == 1
    cmd = cmds[0]
    assert cmd.status == "delivered"
    assert cmd.delivered_at is not None

    # Cannot be consumed automatically
    from app.database import session_factory
    with session_factory() as session:
        c = session.get(Command, cmd.id)
        assert c.status == "delivered"

    # Explicit consumption
    consumed = mark_command_consumed(cmd.id)
    assert consumed is True
    with session_factory() as session:
        c = session.get(Command, cmd.id)
        assert c.status == "consumed"


def test_concurrent_competing_polling_claims():
    """Verify that when competing polling requests attempt to claim commands, exactly one wins.

    Simulates concurrent workers calling get_pending_commands with mark_as_delivered=True.
    """
    import concurrent.futures

    rec = create_recommendation(
        site_id="laptop-01",
        action_type="cpu_cap",
        cap_pct=50,
        action_id="act-race-claim-1",
    )
    approve_recommendation(rec.id)

    results = []
    # Launch two competing workers simultaneously
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(get_pending_commands, "laptop-01", True)
        f2 = executor.submit(get_pending_commands, "laptop-01", True)
        results = [f1.result(), f2.result()]

    total_claimed = sum(len(r) for r in results)
    # Exactly one worker should have successfully claimed the command
    assert total_claimed == 1
    winner = [r for r in results if len(r) == 1][0]
    loser = [r for r in results if len(r) == 0][0]
    assert winner[0].action_id == "act-race-claim-1"
    assert winner[0].status == "delivered"
    assert len(loser) == 0


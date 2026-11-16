"""Unit tests for recommendation, decision, approval and dismissal service."""

from app.models import Recommendation, Decision, Command, AuditRecord
from app.services.action_service import (
    create_recommendation,
    approve_recommendation,
    dismiss_recommendation,
)
from app.database import session_factory
from sqlalchemy import select


def test_create_recommendation():
    """Verify recommendation creation and its audit record generation."""
    rec = create_recommendation(
        site_id="laptop-01",
        action_type="cpu_cap",
        cap_pct=50,
        reason="Test high risk condition",
        action_id="a-test-1",
    )
    assert rec.id is not None
    assert rec.site_id == "laptop-01"
    assert rec.action_id == "a-test-1"
    assert rec.action_type == "cpu_cap"
    assert rec.cap_pct == 50
    assert rec.status == "pending"

    # Verify audit record was created atomically
    with session_factory() as session:
        audits = session.execute(
            select(AuditRecord).where(
                AuditRecord.site_id == "laptop-01",
                AuditRecord.event == "recommendation",
            )
        ).scalars().all()
        assert len(audits) >= 1


def test_approve_recommendation_lifecycle():
    """Verify approval updates state, records decision, creates command and audit."""
    rec = create_recommendation(
        site_id="laptop-01",
        action_type="cpu_cap",
        cap_pct=50,
        action_id="a-approve-1",
    )

    result = approve_recommendation(
        rec_id=rec.id,
        operator="alice",
        reason="Confirmed thermal spike",
    )

    assert result["approved"] is True
    assert result["operator"] == "alice"
    assert result["rec_id"] == rec.id
    assert result["command_delivered"] is False

    with session_factory() as session:
        # Check recommendation status
        updated_rec = session.get(Recommendation, rec.id)
        assert updated_rec.status == "approved"
        assert updated_rec.approver == "alice"
        assert updated_rec.approved_at is not None

        # Check Decision record
        decision = session.execute(
            select(Decision).where(Decision.recommendation_id == rec.id)
        ).scalar_one_or_none()
        assert decision is not None
        assert decision.decision == "approve"
        assert decision.operator == "alice"
        assert decision.site_id == "laptop-01"

        # Check pending Command was created for cpu_cap
        cmd = session.execute(
            select(Command).where(Command.action_id == "a-approve-1")
        ).scalar_one_or_none()
        assert cmd is not None
        assert cmd.status == "pending"
        assert cmd.command_type == "cpu_cap"

        # Check AuditRecord
        audit = session.execute(
            select(AuditRecord).where(
                AuditRecord.site_id == "laptop-01",
                AuditRecord.event == "approval",
            )
        ).scalars().first()
        assert audit is not None
        assert audit.outcome == "success"


def test_approve_by_action_id_string():
    """Verify that approval works when passing the string action_id."""
    rec = create_recommendation(
        site_id="laptop-01",
        action_type="cpu_cap",
        cap_pct=40,
        action_id="a-string-id",
    )

    result = approve_recommendation(
        rec_id="a-string-id",
        operator="bob",
    )
    assert result["approved"] is True
    assert result["rec_id"] == rec.id


def test_dismiss_recommendation_lifecycle():
    """Verify dismissal updates state, records decision, audit, and never creates a command."""
    rec = create_recommendation(
        site_id="laptop-01",
        action_type="cpu_cap",
        cap_pct=50,
        action_id="a-dismiss-1",
    )

    result = dismiss_recommendation(
        rec_id=rec.id,
        operator="carol",
        reason="False positive alarm",
    )

    assert result["dismissed"] is True
    assert result["command_delivered"] is False

    with session_factory() as session:
        updated_rec = session.get(Recommendation, rec.id)
        assert updated_rec.status == "dismissed"
        assert updated_rec.dismissed_at is not None

        # Check Decision record
        decision = session.execute(
            select(Decision).where(Decision.recommendation_id == rec.id)
        ).scalar_one_or_none()
        assert decision is not None
        assert decision.decision == "dismiss"

        # Ensure NO command was created
        cmd = session.execute(
            select(Command).where(Command.action_id == "a-dismiss-1")
        ).scalar_one_or_none()
        assert cmd is None

        # Check AuditRecord was persisted
        audit = session.execute(
            select(AuditRecord).where(
                AuditRecord.site_id == "laptop-01",
                AuditRecord.event == "dismissal",
            )
        ).scalars().first()
        assert audit is not None


def test_duplicate_approval_rejected():
    """Verify that approving an already approved recommendation is rejected."""
    rec = create_recommendation(site_id="laptop-01", action_type="cpu_cap", cap_pct=50)

    res1 = approve_recommendation(rec.id, operator="op1")
    assert res1["approved"] is True

    res2 = approve_recommendation(rec.id, operator="op2")
    assert res2["approved"] is False
    assert res2["status_code"] == 400


def test_duplicate_dismissal_rejected():
    """Verify that dismissing an already dismissed recommendation is rejected."""
    rec = create_recommendation(site_id="laptop-01", action_type="cpu_cap", cap_pct=50)

    res1 = dismiss_recommendation(rec.id, operator="op1")
    assert res1["dismissed"] is True

    res2 = dismiss_recommendation(rec.id, operator="op2")
    assert res2["dismissed"] is False
    assert res2["status_code"] == 400


def test_dismiss_after_approval_rejected():
    """Verify that dismissing an already approved recommendation is rejected."""
    rec = create_recommendation(site_id="laptop-01", action_type="cpu_cap", cap_pct=50)
    approve_recommendation(rec.id)

    res = dismiss_recommendation(rec.id)
    assert res["dismissed"] is False
    assert res["status_code"] == 400


def test_approve_nonexistent_recommendation():
    """Verify that approving a non-existent recommendation returns 404."""
    res = approve_recommendation(99999)
    assert res["approved"] is False
    assert res["status_code"] == 404


"""Action recommendation and approval service for HaritAyush backend."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select

from app.models import Recommendation, Decision, AuditRecord, Command
from app.schemas import ApprovalPayload
from app.database import session_factory


def _find_recommendation(session, rec_id: int | str) -> Recommendation | None:
    """Find a recommendation by numeric ID or action_id."""
    if isinstance(rec_id, int) or (isinstance(rec_id, str) and rec_id.isdigit()):
        rec = session.get(Recommendation, int(rec_id))
        if rec is not None:
            return rec
    if isinstance(rec_id, str):
        rec = session.execute(
            select(Recommendation)
            .where(Recommendation.action_id == rec_id)
            .order_by(Recommendation.created_at.desc(), Recommendation.id.desc())
        ).scalars().first()
        return rec
    return None


def create_recommendation(
    site_id: str,
    action_type: str,
    cap_pct: int,
    reason: str | None = None,
    action_id: str | None = None,
) -> Recommendation:
    """Create a new pending recommendation for an operator-approved action.

    Atomically creates the recommendation and its audit trail entry in a single transaction.
    """
    now = datetime.now(timezone.utc)
    assigned_action_id = action_id or f"a-{now.strftime('%H%M%S')}"

    rec = Recommendation(
        site_id=site_id,
        action_id=assigned_action_id,
        action_type=action_type,
        cap_pct=cap_pct,
        status="pending",
        reason=reason or f"Recommended when risk is elevated: {action_type}",
        created_at=now,
    )

    with session_factory() as session:
        session.add(rec)
        session.flush()

        audit = AuditRecord(
            site_id=site_id,
            event="recommendation",
            payload=json.dumps({
                "rec_id": rec.id,
                "action_id": rec.action_id,
                "action_type": action_type,
                "cap_pct": cap_pct,
                "reason": rec.reason,
            }),
            outcome=None,
        )
        session.add(audit)
        session.commit()
        session.refresh(rec)

    return rec


def approve_recommendation(
    rec_id: int | str,
    operator: str | None = None,
    reason: str | None = None,
) -> dict:
    """Approve a pending recommendation and create a pending command.

    Per PRD §5.D, §5.E, §10:
    - Only an existing pending recommendation may be approved.
    - Preserve the operator's name and decision time.
    - Record the decision in the audit trail.
    - Ensure that approval is required before the agent receives the cpu_cap command.
    - Ensure that dismissal never results in command delivery.
    - Prevent duplicate approval/dismissal decisions.
    - All state changes and audit records are committed atomically.
    """
    with session_factory() as session:
        result = _find_recommendation(session, rec_id)
        if result is None:
            return {
                "approved": False,
                "status_code": 404,
                "error": f"Recommendation '{rec_id}' not found",
            }

        if result.status != "pending":
            return {
                "approved": False,
                "status_code": 400,
                "error": f"Recommendation '{rec_id}' is not pending (status: {result.status})",
            }

        # Check for existing decision record
        existing_decision = session.execute(
            select(Decision).where(Decision.recommendation_id == result.id)
        ).scalars().first()

        if existing_decision:
            return {
                "approved": False,
                "status_code": 400,
                "error": f"Decision '{existing_decision.decision}' already recorded for recommendation '{rec_id}'",
            }

        now = datetime.now(timezone.utc)
        op_name = operator or "operator"

        # Create the approval decision
        decision = Decision(
            recommendation_id=result.id,
            site_id=result.site_id,
            decision="approve",
            operator=op_name,
            decision_time=now,
            reason=reason,
        )
        session.add(decision)

        result.status = "approved"
        result.approved_at = now
        result.approver = op_name

        # Create audit record for approval
        audit = AuditRecord(
            site_id=result.site_id,
            event="approval",
            payload=json.dumps({
                "rec_id": result.id,
                "action_id": result.action_id,
                "operator": op_name,
                "reason": reason,
            }),
            outcome="success",
        )
        session.add(audit)

        # If cpu_cap action, create pending command for the agent
        if result.action_type == "cpu_cap":
            cmd = Command(
                site_id=result.site_id,
                action_id=result.action_id,
                command_type="cpu_cap",
                status="pending",
                created_at=now,
            )
            session.add(cmd)

        # Atomic commit for recommendation, decision, audit record, and command
        session.commit()
        session.refresh(result)

        return {
            "approved": True,
            "status_code": 200,
            "rec_id": result.id,
            "site_id": result.site_id,
            "operator": op_name,
            "decision_time": decision.decision_time.isoformat(),
            "command_delivered": False,
        }


def dismiss_recommendation(
    rec_id: int | str,
    operator: str | None = None,
    reason: str | None = None,
) -> dict:
    """Dismiss a pending recommendation.

    Per PRD §5.D, §5.E, §10:
    - Dismissal never results in command delivery.
    - Record the decision in the audit trail.
    - Prevent duplicate or contradictory decisions.
    - All state changes and audit records are committed atomically.
    """
    with session_factory() as session:
        result = _find_recommendation(session, rec_id)
        if result is None:
            return {
                "dismissed": False,
                "status_code": 404,
                "error": f"Recommendation '{rec_id}' not found",
            }

        if result.status != "pending":
            return {
                "dismissed": False,
                "status_code": 400,
                "error": f"Recommendation '{rec_id}' is not pending (status: {result.status})",
            }

        # Check for existing decision record
        existing_decision = session.execute(
            select(Decision).where(Decision.recommendation_id == result.id)
        ).scalars().first()

        if existing_decision:
            return {
                "dismissed": False,
                "status_code": 400,
                "error": f"Decision '{existing_decision.decision}' already recorded for recommendation '{rec_id}'",
            }

        now = datetime.now(timezone.utc)
        op_name = operator or "operator"

        # Create the dismissal decision
        decision = Decision(
            recommendation_id=result.id,
            site_id=result.site_id,
            decision="dismiss",
            operator=op_name,
            decision_time=now,
            reason=reason,
        )
        session.add(decision)

        result.status = "dismissed"
        result.dismissed_at = now
        result.approver = op_name

        # Audit record for dismissal
        audit = AuditRecord(
            site_id=result.site_id,
            event="dismissal",
            payload=json.dumps({
                "rec_id": result.id,
                "action_id": result.action_id,
                "operator": op_name,
                "reason": reason,
            }),
            outcome="success",
        )
        session.add(audit)

        # Atomic commit for recommendation, decision, and audit record
        session.commit()
        session.refresh(result)

        return {
            "dismissed": True,
            "status_code": 200,
            "rec_id": result.id,
            "site_id": result.site_id,
            "operator": op_name,
            "decision_time": decision.decision_time.isoformat(),
            "command_delivered": False,
        }
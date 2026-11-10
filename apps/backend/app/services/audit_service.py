"""Audit service for HaritAyush backend — audit record persistence and retrieval."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select

from app.models import AuditRecord
from app.database import session_factory


def record_audit(
    site_id: str,
    event: str,
    payload: dict | list | str | None = None,
    outcome: str | None = None,
) -> int:
    """Ingest an audit record from the agent.

    Per PRD §5.F:
    - Recommendation, Decision, Approver, Reason, Action
    - Before readings, After readings, Outcome
    - Backend distinguishes: Recommendation generated, Recommendation approved,
      Recommendation dismissed, Command delivered, Action executed, Action failed or
      rolled back.

    Returns the assigned record ID.
    """
    if payload is not None:
        payload_str = payload if isinstance(payload, str) else json.dumps(payload)
    else:
        payload_str = None

    audit = AuditRecord(
        site_id=site_id,
        event=event,
        payload=payload_str,
        outcome=outcome,
    )

    with session_factory() as session:
        session.add(audit)
        session.commit()
        session.refresh(audit)
        return audit.id


def get_audit_records(
    site_id: str,
    event_type: str | None = None,
    limit: int = 100,
) -> list:
    """Retrieve audit records for a device, in chronological order.

    Per PRD §5.F:
    - Recommendation, Decision, Approver, Reason, Action
    - Before readings, After readings, Outcome
    - Backend distinguishes: Recommendation generated, Recommendation approved,
      Recommendation dismissed, Command delivered, Action executed, Action failed or
      rolled back.

    Returns list of AuditRecord objects.
    """
    with session_factory() as session:
        stmt = select(AuditRecord).where(AuditRecord.site_id == site_id)

        if event_type:
            stmt = stmt.where(AuditRecord.event == event_type)

        # Retrieve the most recent `limit` audit records and sort chronologically
        stmt = stmt.order_by(AuditRecord.ts.desc(), AuditRecord.id.desc()).limit(limit)
        result = session.execute(stmt)
        records = list(result.scalars().all())

    records.reverse()
    return records
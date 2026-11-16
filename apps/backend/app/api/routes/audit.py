"""POST /audit and GET /audit endpoints.

Agent → Backend for audit ingestion.  Dashboard → Backend for audit retrieval.
Per PRD section 5.F:
- Recommendation, Decision, Approver, Reason, Action
- Before readings, After readings, Outcome
- Backend distinguishes: Recommendation generated, Recommendation approved,
  Recommendation dismissed, Command delivered, Action executed, Action failed or
  rolled back.
"""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Body, Query

from ...schemas import AuditRecordCreate, AuditRecordResponse
from ...models import AuditRecord
from ...services.audit_service import record_audit, get_audit_records


router = APIRouter(tags=["audit"])


@router.post(
    "",
    summary="Ingest audit record from agent",
    description="Receive an audit trail entry from the Windows agent.  Events "
    "include: recommendation generated, recommendation approved, "
    "recommendation dismissed, command delivered, action executed, action failed "
    "or rolled back.",
)
async def create_audit_record(
    record: AuditRecordCreate = Body(..., description="Audit record to ingest"),
):
    """Ingest an audit record from the agent."""
    rid = record_audit(
        site_id=record.site_id,
        event=record.event,
        payload=record.payload,
        outcome=record.outcome,
    )
    return {"id": rid, "status": "ingested"}


@router.get(
    "",
    response_model=List[AuditRecordResponse],
    summary="Retrieve audit records",
    description="Retrieve audit records for a device.  Supports filtering by "
    "event type and time range.  Returns records in chronological order.",
)
async def get_audit_records_endpoint(
    site_id: str = Query("laptop-01", description="Site/device identifier"),
    event_type: str = Query(None, description="Filter by event type"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum records to return"),
):
    """Retrieve audit records for a device."""
    import json as _json
    records = get_audit_records(site_id=site_id, event_type=event_type, limit=limit)
    results = []
    for record in records:
        payload_val = None
        if record.payload:
            try:
                payload_val = _json.loads(record.payload)
            except Exception:
                payload_val = {"raw": record.payload}
        ts_str = record.ts.isoformat() if hasattr(record.ts, "isoformat") else str(record.ts) if record.ts else None
        results.append(AuditRecordResponse(
            id=record.id,
            site_id=record.site_id,
            event=record.event,
            payload=payload_val,
            outcome=record.outcome,
            ts=ts_str or "",
        ))
    return results
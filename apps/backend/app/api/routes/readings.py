"""POST /readings — Windows Agent telemetry ingestion.

Receives hardware telemetry from the Windows local agent, validates the
payload, and stores valid readings in the database. Honours the contract
in section 5.A of the final PRD.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.schemas import ReadingPayload, ReadingRecent
from app.models import Reading, AuditRecord
from app.services.reading_service import store_reading
from app.services.audit_service import record_audit


router = APIRouter(tags=["telemetry"])


@router.post(
    "",
    response_model=ReadingRecent,
    summary="Ingest Windows agent telemetry",
    description="Receive real laptop telemetry from the Windows agent. Validates "
    "the incoming payload, preserves timestamps, temperature status and the "
    "unavailable sensor list. Rejects malformed data and never manufactures "
    "missing sensor values.",
)
async def create_reading(payload: ReadingPayload):
    """Store a validated telemetry reading from the Windows agent."""
    try:
        ts = datetime.fromisoformat(payload.ts.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=400,
            detail="Invalid ISO-8601 timestamp format",
        )

    reading = Reading(
        site_id=payload.site_id,
        ts=ts,
        cpu_pct=payload.cpu_pct,
        mem_pct=payload.mem_pct,
        cpu_temp_c=payload.cpu_temp_c,
        temp_status=payload.temp_status,
        unavailable=json.dumps(payload.unavailable) if payload.unavailable else None,
        demo_job=json.dumps(payload.demo_job) if payload.demo_job else None,
    )

    reading_id = store_reading(reading)

    # Audit record: ingestion event
    record_audit(
        site_id=payload.site_id,
        event="telemetry_ingestion",
        payload=payload.model_dump(),
        outcome=None,
    )

    return ReadingRecent(
        id=reading_id,
        site_id=payload.site_id,
        ts=payload.ts,
        cpu_pct=payload.cpu_pct,
        mem_pct=payload.mem_pct,
        cpu_temp_c=payload.cpu_temp_c,
        temp_status=payload.temp_status,
        unavailable=payload.unavailable if payload.unavailable else None,
        demo_job=payload.demo_job if payload.demo_job else None,
    )
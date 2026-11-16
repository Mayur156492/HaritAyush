"""Pydantic schemas for HaritAyush backend API contract per PRD."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field, field_validator


class ReadingPayload(BaseModel):
    """Payload for POST /readings — Windows Agent telemetry."""
    site_id: str = Field(..., min_length=1, description="Site/device identifier, e.g. laptop-01")
    ts: str = Field(..., description="ISO-8601 timestamp, e.g. 2026-11-11T10:15:30Z")
    cpu_pct: float = Field(..., ge=0, le=100, description="CPU utilisation percentage")
    mem_pct: float = Field(..., ge=0, le=100, description="Memory utilisation percentage")
    cpu_temp_c: Optional[float] = Field(
        None,
        ge=-100,
        le=200,
        description="CPU temperature in celsius; may be null if unavailable",
    )
    temp_status: str = Field(
        ...,
        description="Status of the temperature reading: measured, estimated, or unavailable",
    )
    unavailable: List[str] = Field(
        default_factory=list,
        description="Sensor names that are unavailable, e.g. [\"gpu_temp\",\"fan_rpm\"]",
    )
    demo_job: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional demo job metadata {running: bool, cap_pct: int}",
    )

    model_config = {"validate_by_name": True, "str_strip_whitespace": True}

    @field_validator("temp_status")
    @classmethod
    def validate_temp_status(cls, v: str) -> str:
        valid_statuses = {"measured", "estimated", "unavailable"}
        if v not in valid_statuses:
            raise ValueError(f"temp_status must be one of {valid_statuses}, got '{v}'")
        return v

    @field_validator("ts")
    @classmethod
    def validate_ts(cls, v: str) -> str:
        try:
            parsed = datetime.fromisoformat(v.replace("Z", "+00:00"))
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Invalid ISO-8601 timestamp format: {v}") from exc

        now = datetime.now(timezone.utc)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        # Rejects timestamps too far in the future (> 60 seconds)
        if parsed > now + timedelta(seconds=60):
            raise ValueError("Timestamp cannot be in the future")
        return v


class ForecastContract(BaseModel):
    """Contract returned by GET /forecast/latest."""
    ts: str = Field(..., description="Forecast generation timestamp")
    now_temp_c: float = Field(..., description="Current measured/estimated temperature")
    pred: Dict[str, Dict[str, float]] = Field(
        ...,
        description="Per-horizon forecast {5: {mid, lo, hi}, 15: {mid, lo, hi}}",
    )
    limit_c: float = Field(..., description="Danger temperature threshold in celsius")
    risk: str = Field(..., description="Risk level: Normal|Elevated|High")
    time_to_danger_min: int = Field(
        ...,
        ge=0,
        description="Minutes until temperature reaches limit_c via upper forecast trajectory",
    )
    trust: str = Field(
        ...,
        description="Trust level: low|medium|high based on verification outcome",
    )
    why: List[Dict[str, Any]] = Field(
        ...,
        description="Ranked causes with plain-language descriptions and weights",
    )
    action: Optional[Dict[str, Any]] = Field(
        None,
        description="Pending recommended action with id, type, cap_pct and status pending",
    )
    data_mode: str = Field(
        "live",
        description="Data source mode: 'live' for real telemetry, 'replay' for saved-file demo",
    )

    model_config = {"validate_by_name": True, "str_strip_whitespace": True}


class ReadingRecent(BaseModel):
    """Single reading returned by GET /readings/recent."""
    id: int
    site_id: str
    ts: str
    cpu_pct: float
    mem_pct: float
    cpu_temp_c: Optional[float]
    temp_status: str
    unavailable: Optional[List[str]]
    demo_job: Optional[Dict[str, Any]]

    model_config = {"from_attributes": True, "str_strip_whitespace": True}


class RecentReadingsResponse(BaseModel):
    """Response for GET /readings/recent?n=120."""
    site_id: str
    n: int
    readings: List[ReadingRecent]


class ApprovalPayload(BaseModel):
    """Payload for POST /actions/{id}/approve or dismiss."""
    operator: Optional[str] = Field(
        None,
        description="Operator name or identifier making the decision",
    )
    reason: Optional[str] = Field(
        None,
        description="Optional reason for approval or dismissal",
    )


class CommandItem(BaseModel):
    """Single command representation within the envelope."""
    id: int
    type: str  # e.g. "cpu_cap", "start_job", "stop_job"
    issued_at: str
    status: str = "delivered"
    action_id: Optional[str] = None
    cap_pct: Optional[int] = None
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None


class CommandPendingResponse(BaseModel):
    """Envelope response for GET /commands/pending."""
    commands: List[CommandItem]


class CommandPending(BaseModel):
    """Legacy/compatibility representation of a pending command."""
    id: Optional[int] = None
    action_id: Optional[str] = None
    command_type: str
    cap_pct: Optional[int] = Field(None, description="CPU cap percentage for cpu_cap")
    status: str = "pending"
    created_at: str



class AuditRecordCreate(BaseModel):
    """Payload for POST /audit — agent submitting an audit record."""
    site_id: str
    event: str  # "recommendation"|"approval"|"dismissal"|"command_delivered"|"action_executed"|"action_failed"
    payload: Optional[Dict[str, Any]] = None
    outcome: Optional[str] = None  # "success"|"failed"|"rolled_back"


class AuditRecordResponse(BaseModel):
    """Response for GET /audit."""
    id: int
    site_id: str
    event: str
    payload: Optional[Dict[str, Any]]
    outcome: Optional[str]
    ts: str

    model_config = {"from_attributes": True}
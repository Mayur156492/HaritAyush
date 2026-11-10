"""Persistence models for HaritAyush backend."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    Boolean,
    ForeignKey,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for all SQLAlchemy models."""


class Reading(Base):
    """A single telemetry reading from a Windows agent."""
    __tablename__ = "readings"

    id = Column(Integer, primary_key=True, index=True)
    site_id = Column(String, nullable=False)
    ts = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    cpu_pct = Column(Float, nullable=False)
    mem_pct = Column(Float, nullable=False)
    cpu_temp_c = Column(Float, nullable=True)
    temp_status = Column(String, nullable=False, default="measured")
    unavailable = Column(Text, nullable=True)
    demo_job = Column(Text, nullable=True)

    def to_dict(self) -> dict:
        import json
        return {
            "id": self.id,
            "site_id": self.site_id,
            "ts": self.ts.isoformat() if self.ts else None,
            "cpu_pct": self.cpu_pct,
            "mem_pct": self.mem_pct,
            "cpu_temp_c": self.cpu_temp_c,
            "temp_status": self.temp_status,
            "unavailable": json.loads(self.unavailable) if self.unavailable else None,
            "demo_job": json.loads(self.demo_job) if self.demo_job else None,
        }


class Forecast(Base):
    """A temperature forecast for a device at a given horizon."""
    __tablename__ = "forecasts"

    id = Column(Integer, primary_key=True, index=True)
    site_id = Column(String, nullable=False)
    ts = Column(DateTime(timezone=True), nullable=False)
    horizon = Column(String, nullable=False)
    mid = Column(Float, nullable=False)
    lo = Column(Float, nullable=False)
    hi = Column(Float, nullable=False)
    trust = Column(String, nullable=False, default="low")
    why = Column(Text, nullable=True)
    limit_c = Column(Float, nullable=True)
    risk = Column(String, nullable=True)
    time_to_danger_min = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def to_dict(self) -> dict:
        return {
            "horizon": self.horizon,
            "mid": self.mid,
            "lo": self.lo,
            "hi": self.hi,
            "trust": self.trust,
            "why": self.why,
            "limit_c": self.limit_c,
            "risk": self.risk,
            "time_to_danger_min": self.time_to_danger_min,
        }


class Recommendation(Base):
    """A pending recommendation for an operator-approved action."""
    __tablename__ = "recommendations"

    id = Column(Integer, primary_key=True, index=True)
    site_id = Column(String, nullable=False)
    action_id = Column(String, nullable=False)
    action_type = Column(String, nullable=False)
    cap_pct = Column(Integer, nullable=False)
    status = Column(String, nullable=False, default="pending")
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    approved_at = Column(DateTime(timezone=True), nullable=True)
    dismissed_at = Column(DateTime(timezone=True), nullable=True)
    approver = Column(String, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "site_id": self.site_id,
            "action_id": self.action_id,
            "action_type": self.action_type,
            "cap_pct": self.cap_pct,
            "status": self.status,
            "reason": self.reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "dismissed_at": self.dismissed_at.isoformat() if self.dismissed_at else None,
            "approver": self.approver,
        }


class Decision(Base):
    """An operator's approval or dismissal of a recommendation."""
    __tablename__ = "decisions"

    id = Column(Integer, primary_key=True, index=True)
    site_id = Column(String, nullable=False)
    recommendation_id = Column(Integer, ForeignKey("recommendations.id"), nullable=False)
    decision = Column(String, nullable=False)
    operator = Column(String, nullable=True)
    decision_time = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    reason = Column(Text, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "site_id": self.site_id,
            "recommendation_id": self.recommendation_id,
            "decision": self.decision,
            "operator": self.operator,
            "decision_time": self.decision_time.isoformat() if self.decision_time else None,
            "reason": self.reason,
        }


class Command(Base):
    """A command to be sent to the Windows agent."""
    __tablename__ = "commands"

    id = Column(Integer, primary_key=True, index=True)
    site_id = Column(String, nullable=False)
    action_id = Column(String, nullable=False)
    command_type = Column(String, nullable=False)
    status = Column(String, nullable=False, default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    delivered_at = Column(DateTime(timezone=True), nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "site_id": self.site_id,
            "action_id": self.action_id,
            "command_type": self.command_type,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None,
        }


class AuditRecord(Base):
    """An audit trail entry recording recommendation/decision/action/outcome."""
    __tablename__ = "audit_records"

    id = Column(Integer, primary_key=True, index=True)
    site_id = Column(String, nullable=False)
    event = Column(String, nullable=False)
    payload = Column(Text, nullable=True)
    outcome = Column(String, nullable=True)
    ts = Column(DateTime(timezone=True), server_default=func.now())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "site_id": self.site_id,
            "event": self.event,
            "payload": self.payload,
            "outcome": self.outcome,
            "ts": self.ts.isoformat() if self.ts else None,
        }
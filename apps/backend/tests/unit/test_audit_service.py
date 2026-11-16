"""Unit tests for audit service persistence and retrieval."""

from app.models import AuditRecord
from app.services.audit_service import record_audit, get_audit_records


def test_record_and_get_audit():
    """Verify audit record persistence and deserialization."""
    payload = {"reading_id": 12, "temp": 75.5}
    aid = record_audit(
        site_id="laptop-01",
        event="telemetry_ingestion",
        payload=payload,
        outcome="success",
    )
    assert aid is not None

    records = get_audit_records("laptop-01")
    assert len(records) >= 1
    matching = [r for r in records if r.id == aid]
    assert len(matching) == 1
    assert matching[0].event == "telemetry_ingestion"
    assert matching[0].outcome == "success"


def test_audit_records_event_filtering():
    """Verify filtering audit records by event type."""
    record_audit(site_id="laptop-01", event="event_a", payload={"data": 1})
    record_audit(site_id="laptop-01", event="event_b", payload={"data": 2})
    record_audit(site_id="laptop-01", event="event_a", payload={"data": 3})

    a_records = get_audit_records("laptop-01", event_type="event_a")
    assert len(a_records) == 2
    for r in a_records:
        assert r.event == "event_a"

    b_records = get_audit_records("laptop-01", event_type="event_b")
    assert len(b_records) == 1
    assert b_records[0].event == "event_b"


def test_audit_chronological_ordering():
    """Verify audit records are returned in chronological order (oldest to newest)."""
    for i in range(5):
        record_audit(site_id="laptop-01", event=f"step_{i}", payload={"step": i})

    records = get_audit_records("laptop-01")
    steps = [r.event for r in records if r.event.startswith("step_")]
    assert steps == ["step_0", "step_1", "step_2", "step_3", "step_4"]


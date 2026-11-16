"""Integration tests for end-to-end recommendation, command, and audit lifecycle consistency."""

from datetime import datetime, timezone
from app.models import Reading, Recommendation, Decision, Command, AuditRecord
from app.database import session_factory
from sqlalchemy import select


def test_full_recommendation_and_command_lifecycle(client, sample_reading_payload):
    """End-to-end verification of the Core Loop: Predict -> Recommend -> Approve -> Command -> Audit."""
    # 1. Telemetry Ingestion
    ingest_resp = client.post("/readings", json=sample_reading_payload)
    assert ingest_resp.status_code == 200

    # 2. Check Forecast & Recommended Action
    fc_resp = client.get("/forecast/latest?site_id=laptop-01")
    assert fc_resp.status_code == 200
    fc_data = fc_resp.json()
    action = fc_data["action"]
    action_id = action["id"]
    assert action["status"] == "pending"

    # 3. Verify that BEFORE approval, pending commands is EMPTY (PRD section 5.E: do not deliver pending recs)
    cmd_resp_before = client.get("/commands/pending?site_id=laptop-01")
    assert cmd_resp_before.status_code == 200
    assert cmd_resp_before.json() == []

    # 4. Operator approves the recommendation
    app_resp = client.post(
        f"/actions/{action_id}/approve",
        json={"operator": "lead_operator", "reason": "Confirmed temperature rising towards limit"},
    )
    assert app_resp.status_code == 200
    app_data = app_resp.json()
    assert app_data["status"] == "approved"
    assert app_data["operator"] == "lead_operator"
    assert app_data["command_delivered"] is False

    # 5. Verify that AFTER approval, pending commands contains the approved cpu_cap command
    cmd_resp_after = client.get("/commands/pending?site_id=laptop-01")
    assert cmd_resp_after.status_code == 200
    cmds = cmd_resp_after.json()
    assert len(cmds) == 1
    assert cmds[0]["action_id"] == action_id
    assert cmds[0]["command_type"] == "cpu_cap"
    assert cmds[0]["cap_pct"] == 50
    assert cmds[0]["status"] == "pending"

    # 6. Verify Audit Records for each event in the lifecycle
    with session_factory() as session:
        # We should have telemetry_ingestion, recommendation, and approval events
        events = session.execute(
            select(AuditRecord.event).where(AuditRecord.site_id == "laptop-01")
        ).scalars().all()
        assert "telemetry_ingestion" in events
        assert "approval" in events


def test_dismissal_lifecycle_and_audit(client, sample_reading_payload):
    """Verify dismissal generates audit record and NEVER creates a pending command."""
    client.post("/readings", json=sample_reading_payload)
    fc_resp = client.get("/forecast/latest?site_id=laptop-01")
    action_id = fc_resp.json()["action"]["id"]

    # Dismiss recommendation
    dism_resp = client.post(
        f"/actions/{action_id}/dismiss",
        json={"operator": "safety_officer", "reason": "Cooling fans already restored"},
    )
    assert dism_resp.status_code == 200
    assert dism_resp.json()["status"] == "dismissed"
    assert dism_resp.json()["command_delivered"] is False

    # Verify no commands were created
    cmd_resp = client.get("/commands/pending?site_id=laptop-01")
    assert cmd_resp.status_code == 200
    assert cmd_resp.json() == []

    # Verify dismissal audit record exists in database
    with session_factory() as session:
        dismiss_audit = session.execute(
            select(AuditRecord).where(
                AuditRecord.site_id == "laptop-01",
                AuditRecord.event == "dismissal",
            )
        ).scalar_one_or_none()
        assert dismiss_audit is not None
        assert dismiss_audit.outcome == "success"


def test_invalid_lifecycle_transitions(client, sample_reading_payload):
    """Verify predictable error handling for invalid or repeated lifecycle operations."""
    client.post("/readings", json=sample_reading_payload)
    fc_resp = client.get("/forecast/latest?site_id=laptop-01")
    action_id = fc_resp.json()["action"]["id"]

    # First dismissal succeeds
    r1 = client.post(f"/actions/{action_id}/dismiss")
    assert r1.status_code == 200

    # Second dismissal should return 400
    r2 = client.post(f"/actions/{action_id}/dismiss")
    assert r2.status_code == 400

    # Approval after dismissal should return 400
    r3 = client.post(f"/actions/{action_id}/approve")
    assert r3.status_code == 400

    # Action on nonexistent ID should return 404
    r4 = client.post("/actions/nonexistent-action-999/approve")
    assert r4.status_code == 404


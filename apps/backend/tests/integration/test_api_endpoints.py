"""Integration tests for all FastAPI endpoints."""

from datetime import datetime, timezone


def test_health_check(client):
    """GET /health reports service status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "haritayush-backend"


def test_post_readings_valid(client, sample_reading_payload):
    """POST /readings ingests telemetry and returns stored reading."""
    response = client.post("/readings", json=sample_reading_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["site_id"] == "laptop-01"
    assert data["cpu_pct"] == 87.5
    assert data["cpu_temp_c"] == 78.0
    assert data["temp_status"] == "measured"
    assert "gpu_temp" in data["unavailable"]
    assert data["demo_job"] == {"running": True, "cap_pct": 100}
    assert "id" in data


def test_post_readings_invalid_timestamp(client, sample_reading_payload):
    """POST /readings rejects invalid timestamp with a 4xx error."""
    payload = dict(sample_reading_payload)
    payload["ts"] = "not-a-timestamp"
    response = client.post("/readings", json=payload)
    # FastAPI/Pydantic returns 422 Unprocessable Entity for field validation errors
    assert response.status_code in (400, 422)


def test_get_readings_recent(client, sample_reading_payload):
    """GET /readings/recent returns chronological history."""
    # First post 3 readings
    for i in range(3):
        p = dict(sample_reading_payload)
        p["cpu_pct"] = 50.0 + i * 10
        client.post("/readings", json=p)

    response = client.get("/readings/recent?site_id=laptop-01&n=120")
    assert response.status_code == 200
    data = response.json()
    assert data["site_id"] == "laptop-01"
    assert data["n"] == 3
    assert len(data["readings"]) == 3
    assert data["readings"][0]["cpu_pct"] == 50.0
    assert data["readings"][2]["cpu_pct"] == 70.0


def test_get_forecast_latest_204_when_no_readings(client):
    """GET /forecast/latest returns 204 if no readings exist for device."""
    response = client.get("/forecast/latest?site_id=nonexistent")
    assert response.status_code == 204
    # HTTP 204 has no body — just verify the status code


def test_get_forecast_latest_contract(client, sample_reading_payload):
    """GET /forecast/latest returns full forecast contract when readings exist."""
    client.post("/readings", json=sample_reading_payload)

    response = client.get("/forecast/latest?site_id=laptop-01")
    assert response.status_code == 200
    data = response.json()

    # Contract verification per PRD Section 4
    assert "ts" in data
    assert "now_temp_c" in data
    assert data["now_temp_c"] == 78.0

    # Predictions for 5 and 15 minute horizons
    assert "pred" in data
    assert "5" in data["pred"]
    assert "15" in data["pred"]
    for h in ("5", "15"):
        assert "mid" in data["pred"][h]
        assert "lo" in data["pred"][h]
        assert "hi" in data["pred"][h]

    assert "limit_c" in data
    assert "risk" in data
    assert "time_to_danger_min" in data
    assert isinstance(data["time_to_danger_min"], int)
    assert "trust" in data
    assert "why" in data
    assert isinstance(data["why"], list)
    assert len(data["why"]) >= 1

    # Action recommendation
    assert "action" in data
    assert data["action"]["type"] == "cpu_cap"
    assert data["action"]["status"] == "pending"
    assert data["action"]["cap_pct"] == 50


def test_actions_approve_and_dismiss_endpoints(client, sample_reading_payload):
    """POST /actions/{rec_id}/approve and /dismiss verify operator lifecycle."""
    # Seed reading and forecast to generate a recommendation
    client.post("/readings", json=sample_reading_payload)
    fc_resp = client.get("/forecast/latest?site_id=laptop-01")
    action_id = fc_resp.json()["action"]["id"]

    # Approve action
    app_resp = client.post(
        f"/actions/{action_id}/approve",
        json={"operator": "lead-op", "reason": "High thermal trend"},
    )
    assert app_resp.status_code == 200
    app_data = app_resp.json()
    assert app_data["status"] == "approved"
    assert app_data["operator"] == "lead-op"
    assert app_data["command_delivered"] is False

    # Check pending commands endpoint contains the approved cpu_cap command
    cmd_resp = client.get("/commands/pending?site_id=laptop-01")
    assert cmd_resp.status_code == 200
    cmds = cmd_resp.json()
    assert len(cmds) == 1
    assert cmds[0]["action_id"] == action_id
    assert cmds[0]["command_type"] == "cpu_cap"
    assert cmds[0]["cap_pct"] == 50
    assert cmds[0]["status"] == "pending"

    # Repeated approval should return 400
    dup_resp = client.post(
        f"/actions/{action_id}/approve",
        json={"operator": "lead-op"},
    )
    assert dup_resp.status_code == 400

    # Dismissing approved action should return 400
    dism_resp = client.post(
        f"/actions/{action_id}/dismiss",
        json={"operator": "lead-op"},
    )
    assert dism_resp.status_code == 400


def test_audit_endpoints(client):
    """POST /audit and GET /audit integration."""
    # Ingest audit event from agent
    post_resp = client.post(
        "/audit",
        json={
            "site_id": "laptop-01",
            "event": "action_executed",
            "payload": {"cap_pct": 50, "target": "demo_job"},
            "outcome": "success",
        },
    )
    assert post_resp.status_code == 200
    assert post_resp.json()["status"] == "ingested"

    # Retrieve audit records
    get_resp = client.get("/audit?site_id=laptop-01&event_type=action_executed")
    assert get_resp.status_code == 200
    records = get_resp.json()
    assert len(records) >= 1
    assert records[0]["event"] == "action_executed"
    assert records[0]["payload"]["cap_pct"] == 50
    assert records[0]["outcome"] == "success"


"""Focused integration tests for Batch 1 reading ingestion, forecast endpoint, and recommendation lifecycle."""

from datetime import datetime, timezone, timedelta
from app.models import Reading, Recommendation
from app.database import session_factory
from sqlalchemy import select


def test_post_readings_cpu_and_mem_bounds(client):
    """Verify POST /readings rejects CPU and memory percentages outside [0, 100]."""
    valid_base = {
        "site_id": "laptop-01",
        "ts": datetime.now(timezone.utc).isoformat(),
        "cpu_pct": 50.0,
        "mem_pct": 50.0,
        "cpu_temp_c": 60.0,
        "temp_status": "measured",
    }

    # cpu_pct > 100
    bad_cpu = dict(valid_base, cpu_pct=105.0)
    assert client.post("/readings", json=bad_cpu).status_code == 422

    # cpu_pct < 0
    bad_cpu_neg = dict(valid_base, cpu_pct=-5.0)
    assert client.post("/readings", json=bad_cpu_neg).status_code == 422

    # mem_pct > 100
    bad_mem = dict(valid_base, mem_pct=100.5)
    assert client.post("/readings", json=bad_mem).status_code == 422


def test_post_readings_rejects_future_timestamps(client):
    """Verify POST /readings rejects timestamps too far in the future (> 60s)."""
    future_ts = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    payload = {
        "site_id": "laptop-01",
        "ts": future_ts,
        "cpu_pct": 50.0,
        "mem_pct": 50.0,
        "cpu_temp_c": 60.0,
        "temp_status": "measured",
    }
    response = client.post("/readings", json=payload)
    assert response.status_code == 422


def test_post_readings_rejects_invalid_temp_status(client):
    """Verify POST /readings rejects invalid temp_status values."""
    payload = {
        "site_id": "laptop-01",
        "ts": datetime.now(timezone.utc).isoformat(),
        "cpu_pct": 50.0,
        "mem_pct": 50.0,
        "cpu_temp_c": 60.0,
        "temp_status": "fabricated_status",
    }
    response = client.post("/readings", json=payload)
    assert response.status_code == 422


def test_post_readings_honest_sensor_values(client):
    """Verify measured, estimated, and unavailable sensor values are honestly persisted."""
    # Unavailable temperature sensor
    payload_unavail = {
        "site_id": "laptop-01",
        "ts": datetime.now(timezone.utc).isoformat(),
        "cpu_pct": 60.0,
        "mem_pct": 40.0,
        "cpu_temp_c": None,
        "temp_status": "unavailable",
        "unavailable": ["cpu_temp", "fan_rpm"],
    }
    resp1 = client.post("/readings", json=payload_unavail)
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["cpu_temp_c"] is None
    assert data1["temp_status"] == "unavailable"
    assert "cpu_temp" in data1["unavailable"]

    # Estimated temperature sensor
    payload_est = {
        "site_id": "laptop-01",
        "ts": datetime.now(timezone.utc).isoformat(),
        "cpu_pct": 75.0,
        "mem_pct": 55.0,
        "cpu_temp_c": 68.0,
        "temp_status": "estimated",
    }
    resp2 = client.post("/readings", json=payload_est)
    assert resp2.status_code == 200
    assert resp2.json()["temp_status"] == "estimated"


def test_get_readings_recent_maximum_1000_limit(client):
    """Verify GET /readings/recent enforces maximum limit of 1000 records."""
    # Valid limit <= 1000
    resp_valid = client.get("/readings/recent?site_id=laptop-01&n=1000")
    assert resp_valid.status_code == 200

    # Limit > 1000 is rejected
    resp_invalid = client.get("/readings/recent?site_id=laptop-01&n=1001")
    assert resp_invalid.status_code == 422


def test_get_readings_recent_empty_history(client):
    """Verify GET /readings/recent on an empty device returns n=0, empty list with status 200."""
    response = client.get("/readings/recent?site_id=nonexistent-device&n=120")
    assert response.status_code == 200
    data = response.json()
    assert data["site_id"] == "nonexistent-device"
    assert data["n"] == 0
    assert data["readings"] == []


def test_get_forecast_latest_204_when_no_readings(client):
    """Verify GET /forecast/latest returns HTTP 204 No Content when no readings exist."""
    response = client.get("/forecast/latest?site_id=brand-new-site")
    assert response.status_code == 204


def test_forecast_risk_and_recommendation_lifecycle(client):
    """Verify forecast returns Normal, Elevated, and High risk and manages recommendations without duplicates."""
    now = datetime.now(timezone.utc)

    # 1. Post a normal temperature reading (50°C) -> Risk should be Normal
    client.post("/readings", json={
        "site_id": "laptop-01",
        "ts": now.isoformat(),
        "cpu_pct": 30.0,
        "mem_pct": 40.0,
        "cpu_temp_c": 50.0,
        "temp_status": "measured",
    })

    fc_normal = client.get("/forecast/latest?site_id=laptop-01")
    assert fc_normal.status_code == 200
    data_normal = fc_normal.json()
    assert data_normal["risk"] == "Normal"
    assert data_normal["time_to_danger_min"] == 0
    # No recommendation pending because risk is Normal
    assert data_normal["action"]["type"] == "none"

    # Verify no recommendation rows were created in DB for Normal risk
    with session_factory() as session:
        recs = session.execute(
            select(Recommendation).where(Recommendation.site_id == "laptop-01")
        ).scalars().all()
        assert len(recs) == 0

    # 2. Post an elevated temperature reading (78°C) -> 15m hi forecast reaches 80°C -> Elevated Risk
    client.post("/readings", json={
        "site_id": "laptop-01",
        "ts": (now + timedelta(seconds=10)).isoformat(),
        "cpu_pct": 85.0,
        "mem_pct": 60.0,
        "cpu_temp_c": 78.0,
        "temp_status": "measured",
    })

    fc_elevated = client.get("/forecast/latest?site_id=laptop-01")
    assert fc_elevated.status_code == 200
    data_elevated = fc_elevated.json()
    assert data_elevated["risk"] == "Elevated"
    assert data_elevated["action"]["type"] == "cpu_cap"
    assert data_elevated["action"]["status"] == "pending"
    action_id_1 = data_elevated["action"]["id"]

    # 3. Query forecast again: must REUSE the existing pending recommendation without creating a duplicate!
    fc_elevated_again = client.get("/forecast/latest?site_id=laptop-01")
    assert fc_elevated_again.status_code == 200
    action_id_2 = fc_elevated_again.json()["action"]["id"]
    assert action_id_1 == action_id_2

    with session_factory() as session:
        recs_count = session.execute(
            select(Recommendation).where(
                Recommendation.site_id == "laptop-01",
                Recommendation.status == "pending",
            )
        ).scalars().all()
        # Exactly 1 pending recommendation exists (no duplicate)
        assert len(recs_count) == 1


"""Integration tests verifying deterministic handling of multiple pending recommendations."""

from datetime import datetime, timezone, timedelta
from app.models import Recommendation
from app.services.action_service import create_recommendation, approve_recommendation
from app.database import session_factory


def test_forecast_with_multiple_pending_recommendations(client, sample_reading_payload):
    """Verify GET /forecast/latest does not raise MultipleResultsFound when multiple pending recommendations exist.

    Uses deterministic selection policy: freshest created_at, id DESC.
    """
    # Seed a reading first so forecast endpoint succeeds
    client.post("/readings", json=sample_reading_payload)

    # Manually insert 3 pending recommendations with different created_at timestamps
    base_time = datetime(2026, 11, 10, 10, 0, 0, tzinfo=timezone.utc)
    with session_factory() as session:
        r1 = Recommendation(
            site_id="laptop-01",
            action_id="rec-old",
            action_type="cpu_cap",
            cap_pct=30,
            status="pending",
            reason="Old recommendation",
            created_at=base_time,
        )
        r2 = Recommendation(
            site_id="laptop-01",
            action_id="rec-middle",
            action_type="cpu_cap",
            cap_pct=40,
            status="pending",
            reason="Middle recommendation",
            created_at=base_time + timedelta(minutes=5),
        )
        r3 = Recommendation(
            site_id="laptop-01",
            action_id="rec-newest",
            action_type="cpu_cap",
            cap_pct=50,
            status="pending",
            reason="Newest recommendation",
            created_at=base_time + timedelta(minutes=10),
        )
        session.add_all([r1, r2, r3])
        session.commit()

    # Call GET /forecast/latest
    # Must NOT fail with MultipleResultsFound (500), and must select the newest recommendation (rec-newest)
    response = client.get("/forecast/latest?site_id=laptop-01")
    assert response.status_code == 200
    data = response.json()

    action = data["action"]
    assert action["status"] == "pending"
    assert action["id"] == "rec-newest"
    assert action["cap_pct"] == 50


def test_id_vs_created_at_deterministic_selection(client, sample_reading_payload):
    """Verify that selection policy prioritizes created_at over database ID.

    Even if an older record has a higher ID (or equal ID condition), the newest timestamp wins.
    """
    client.post("/readings", json=sample_reading_payload)

    t_earlier = datetime(2026, 11, 10, 9, 0, 0, tzinfo=timezone.utc)
    t_later = datetime(2026, 11, 10, 11, 0, 0, tzinfo=timezone.utc)

    # Insert later recommendation first (so it gets lower ID)
    with session_factory() as session:
        r_later = Recommendation(
            site_id="laptop-01",
            action_id="rec-timestamp-newer",
            action_type="cpu_cap",
            cap_pct=70,
            status="pending",
            created_at=t_later,
        )
        session.add(r_later)
        session.commit()

        # Insert earlier recommendation second (so it gets higher ID)
        r_earlier = Recommendation(
            site_id="laptop-01",
            action_id="rec-higher-id-but-older",
            action_type="cpu_cap",
            cap_pct=30,
            status="pending",
            created_at=t_earlier,
        )
        session.add(r_earlier)
        session.commit()

    response = client.get("/forecast/latest?site_id=laptop-01")
    assert response.status_code == 200
    action = response.json()["action"]

    # Deterministic policy must pick rec-timestamp-newer, NOT the higher ID
    assert action["id"] == "rec-timestamp-newer"
    assert action["cap_pct"] == 70


def test_approval_of_selected_multiplicity_recommendation(client, sample_reading_payload):
    """Verify approving the selected newest recommendation transitions it without touching other pending recommendations."""
    client.post("/readings", json=sample_reading_payload)

    t1 = datetime(2026, 11, 10, 10, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 11, 10, 10, 5, 0, tzinfo=timezone.utc)

    with session_factory() as session:
        r1 = Recommendation(
            site_id="laptop-01",
            action_id="rec-1",
            action_type="cpu_cap",
            cap_pct=40,
            status="pending",
            created_at=t1,
        )
        r2 = Recommendation(
            site_id="laptop-01",
            action_id="rec-2",
            action_type="cpu_cap",
            cap_pct=60,
            status="pending",
            created_at=t2,
        )
        session.add_all([r1, r2])
        session.commit()

    # Approve rec-2
    resp = client.post("/actions/rec-2/approve", json={"operator": "op"})
    assert resp.status_code == 200

    # Next forecast query should now select rec-1 (the remaining pending recommendation)
    fc_resp = client.get("/forecast/latest?site_id=laptop-01")
    assert fc_resp.status_code == 200
    assert fc_resp.json()["action"]["id"] == "rec-1"


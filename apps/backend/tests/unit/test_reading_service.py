"""Unit tests for reading storage and retrieval service."""

from datetime import datetime, timezone, timedelta
from app.models import Reading
from app.services.reading_service import store_reading, get_recent_readings


def test_store_and_retrieve_single_reading():
    """Verify that a reading is stored and assigned an ID."""
    ts = datetime.now(timezone.utc)
    reading = Reading(
        site_id="laptop-01",
        ts=ts,
        cpu_pct=45.5,
        mem_pct=52.0,
        cpu_temp_c=65.0,
        temp_status="measured",
        unavailable=None,
        demo_job=None,
    )
    reading_id = store_reading(reading)
    assert reading_id is not None
    assert reading_id > 0

    recent = get_recent_readings("laptop-01", n=10)
    assert len(recent) == 1
    assert recent[0]["id"] == reading_id
    assert recent[0]["site_id"] == "laptop-01"
    assert recent[0]["cpu_pct"] == 45.5
    assert recent[0]["cpu_temp_c"] == 65.0


def test_get_recent_readings_ordering_and_limit():
    """Verify that get_recent_readings returns the n most recent readings in chronological order (oldest to newest)."""
    base_ts = datetime(2026, 11, 10, 12, 0, 0, tzinfo=timezone.utc)
    # Store 10 readings with increasing timestamps
    for i in range(10):
        r = Reading(
            site_id="laptop-01",
            ts=base_ts + timedelta(seconds=i * 5),
            cpu_pct=float(i * 10),
            mem_pct=50.0,
            cpu_temp_c=60.0 + i,
            temp_status="measured",
        )
        store_reading(r)

    # Request only 5 recent readings
    recent = get_recent_readings("laptop-01", n=5)
    assert len(recent) == 5

    # Should contain the 5 latest readings (i=5 through 9) in chronological order
    cpu_pcts = [item["cpu_pct"] for item in recent]
    assert cpu_pcts == [50.0, 60.0, 70.0, 80.0, 90.0]

    # Verify chronological ordering: each ts should be >= previous ts
    for i in range(len(recent) - 1):
        assert recent[i]["ts"] <= recent[i + 1]["ts"]


def test_get_recent_readings_empty():
    """Verify that querying a device with no readings returns an empty list."""
    recent = get_recent_readings("nonexistent-site", n=10)
    assert recent == []


def test_get_recent_readings_site_isolation():
    """Verify that readings from one site do not leak into another."""
    ts = datetime.now(timezone.utc)
    store_reading(Reading(site_id="site-A", ts=ts, cpu_pct=20.0, mem_pct=30.0, cpu_temp_c=50.0))
    store_reading(Reading(site_id="site-B", ts=ts, cpu_pct=80.0, mem_pct=90.0, cpu_temp_c=85.0))

    readings_a = get_recent_readings("site-A", n=10)
    readings_b = get_recent_readings("site-B", n=10)

    assert len(readings_a) == 1
    assert readings_a[0]["site_id"] == "site-A"
    assert readings_a[0]["cpu_pct"] == 20.0

    assert len(readings_b) == 1
    assert readings_b[0]["site_id"] == "site-B"
    assert readings_b[0]["cpu_pct"] == 80.0


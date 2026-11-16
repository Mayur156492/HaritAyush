"""Pytest configuration and isolated fixtures for HaritAyush backend tests."""

import os
import tempfile
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Setup a clean isolated test database file
_test_db_file = os.path.join(tempfile.gettempdir(), f"haritayush_test_{os.getpid()}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_test_db_file}"

import app.database as app_db
# Point engine to the isolated test database
app_db.DATABASE_URL = f"sqlite:///{_test_db_file}"
app_db.engine = create_engine(f"sqlite:///{_test_db_file}", connect_args={"check_same_thread": False})
app_db.session_factory = sessionmaker(autocommit=False, autoflush=False, bind=app_db.engine)

from app.models import Base
from app.main import app


@pytest.fixture(autouse=True)
def setup_test_db():
    """Create all tables before each test and drop them after."""
    Base.metadata.create_all(bind=app_db.engine)
    app_db.init_db()
    yield
    Base.metadata.drop_all(bind=app_db.engine)


@pytest.fixture
def client():
    """FastAPI TestClient fixture."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def sample_reading_payload():
    """Sample telemetry payload matching PRD Section 4."""
    # Use a timestamp 30 seconds in the past to avoid future-timestamp rejection
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "site_id": "laptop-01",
        "ts": ts,
        "cpu_pct": 87.5,
        "mem_pct": 61.2,
        "cpu_temp_c": 78.0,
        "temp_status": "measured",
        "unavailable": ["gpu_temp", "fan_rpm", "inlet_temp", "humidity", "power_w"],
        "demo_job": {"running": True, "cap_pct": 100},
    }


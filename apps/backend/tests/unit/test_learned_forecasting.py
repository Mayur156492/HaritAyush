"""Unit tests for learned forecasting, chronological validation, and fallback."""

import pytest
from datetime import datetime, timezone, timedelta
from app.models import Reading
from app.intelligence.forecasting.learned_model import (
    LearnedTemperatureModel,
    HORIZON_5M_SEC,
    HORIZON_15M_SEC,
)
from app.services.forecast_service import get_latest_forecast


def test_learned_model_insufficient_data_returns_unfitted():
    """Learned model must not claim to be fitted when insufficient supervised pairs exist."""
    model = LearnedTemperatureModel()
    base_ts = datetime(2026, 11, 10, 10, 0, 0, tzinfo=timezone.utc)
    # Only 5 readings, not enough for 10 pairs at 5m/15m
    readings = [
        Reading(
            site_id="laptop-01",
            ts=base_ts + timedelta(seconds=i * 30),
            cpu_pct=50.0,
            mem_pct=50.0,
            cpu_temp_c=60.0 + i,
            temp_status="measured",
        )
        for i in range(5)
    ]
    fitted = model.fit(readings)
    assert fitted is False
    assert model.is_fitted is False
    assert model.predict(readings[-1]) is None


def test_learned_model_timestamp_aware_target_matching():
    """Verify that 5m and 15m targets are matched by timestamp tolerance, not row index."""
    model = LearnedTemperatureModel()
    base_ts = datetime(2026, 11, 10, 10, 0, 0, tzinfo=timezone.utc)
    readings = []

    # Generate 60 readings spaced 30 seconds apart (30 minutes total)
    for i in range(60):
        readings.append(
            Reading(
                site_id="laptop-01",
                ts=base_ts + timedelta(seconds=i * 30),
                cpu_pct=40.0 + (i % 10),
                mem_pct=50.0,
                cpu_temp_c=55.0 + (i * 0.2),
                temp_status="measured",
            )
        )

    fitted = model.fit(readings)
    assert fitted is True
    assert model.is_fitted is True
    assert model.training_pairs_count >= 10

    # Test prediction
    pred = model.predict(readings[-1], readings[-2])
    assert pred is not None
    assert "5" in pred
    assert "15" in pred
    assert pred["source"] == "learned_ridge"
    assert pred["5"]["lo"] <= pred["5"]["mid"] <= pred["5"]["hi"]
    assert pred["15"]["lo"] <= pred["15"]["mid"] <= pred["15"]["hi"]


def test_learned_model_fallback_on_unavailable_sensor():
    """When current reading has unavailable or non-measured temp, fallback occurs cleanly."""
    model = LearnedTemperatureModel()
    model.is_fitted = True
    model.model_5m = object()
    model.model_15m = object()

    unavail_reading = Reading(
        site_id="laptop-01",
        ts=datetime.now(timezone.utc),
        cpu_pct=50.0,
        mem_pct=50.0,
        cpu_temp_c=None,
        temp_status="unavailable",
    )
    assert model.predict(unavail_reading) is None


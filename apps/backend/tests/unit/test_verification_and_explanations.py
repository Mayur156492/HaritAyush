"""Unit tests for forecast verification, confidence estimation, and explanation generation."""

import pytest
from datetime import datetime, timezone, timedelta
from app.models import Reading
from app.intelligence.verification.prediction_validator import verify_prediction
from app.intelligence.verification.confidence import estimate_confidence
from app.services.explanation_service import rank_causes, build_why_payload


def test_verify_prediction_matched_and_error_computed():
    """Verify forecast matches within tolerance and calculates absolute error."""
    target_time = datetime(2026, 11, 10, 12, 15, 0, tzinfo=timezone.utc)
    actual_readings = [
        Reading(
            site_id="laptop-01",
            ts=target_time + timedelta(seconds=15),  # within 60s tolerance
            cpu_pct=60.0,
            mem_pct=50.0,
            cpu_temp_c=74.5,
            temp_status="measured",
        )
    ]
    result = verify_prediction(
        forecast_mid=72.0,
        forecast_target_time=target_time,
        actual_readings=actual_readings,
        tolerance_sec=60,
    )
    assert result["verified"] is True
    assert result["status"] == "verified"
    assert result["observed_temp_c"] == 74.5
    assert result["error_c"] == 2.5


def test_verify_prediction_out_of_tolerance_unverified():
    """Verify that observations outside tolerance window are recorded as unverified."""
    target_time = datetime(2026, 11, 10, 12, 15, 0, tzinfo=timezone.utc)
    actual_readings = [
        Reading(
            site_id="laptop-01",
            ts=target_time + timedelta(seconds=120),  # > 60s tolerance
            cpu_pct=60.0,
            mem_pct=50.0,
            cpu_temp_c=74.5,
            temp_status="measured",
        )
    ]
    result = verify_prediction(
        forecast_mid=72.0,
        forecast_target_time=target_time,
        actual_readings=actual_readings,
        tolerance_sec=60,
    )
    assert result["verified"] is False
    assert result["status"] == "unverified"
    assert result["error_c"] is None


def test_estimate_confidence_insufficient_history():
    """Insufficient verified history (< 5 samples) yields uncalibrated low confidence."""
    current_reading = Reading(
        site_id="laptop-01",
        ts=datetime.now(timezone.utc),
        cpu_pct=50.0,
        mem_pct=50.0,
        cpu_temp_c=65.0,
        temp_status="measured",
    )
    history = [{"verified": True, "error_c": 1.2}]  # Only 1 sample
    conf = estimate_confidence(history, current_reading)
    assert conf["confidence_level"] == "low"
    assert conf["trust"] == "low"
    assert conf["calibrated"] is False


def test_estimate_confidence_sufficient_history():
    """Sufficient low-error verification history calibrates high confidence."""
    current_reading = Reading(
        site_id="laptop-01",
        ts=datetime.now(timezone.utc),
        cpu_pct=50.0,
        mem_pct=50.0,
        cpu_temp_c=65.0,
        temp_status="measured",
    )
    history = [{"verified": True, "error_c": 1.0} for _ in range(6)]
    conf = estimate_confidence(history, current_reading, mae=1.2)
    assert conf["confidence_level"] == "high"
    assert conf["trust"] == "high"
    assert conf["calibrated"] is True
    assert conf["mean_error_c"] == 1.0


def test_rank_causes_no_fabricated_text_and_no_duplicates():
    """Explanations must derive strictly from readings without hardcoded fake claims."""
    reading = Reading(
        site_id="laptop-01",
        ts=datetime.now(timezone.utc),
        cpu_pct=92.0,
        mem_pct=50.0,
        cpu_temp_c=82.0,
        temp_status="measured",
    )
    forecast = {"15": {"hi": 86.0}}
    causes = rank_causes(reading, forecast, limit_c=85.0, trust="high")
    assert len(causes) >= 2
    # Check that fabricated claim is NOT present
    for c in causes:
        assert "rose from 40% to 95% in 3 min" not in c["cause"]
    # Check deduplication
    texts = [c["cause"] for c in causes]
    assert len(texts) == len(set(texts))


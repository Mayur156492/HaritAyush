"""Focused unit tests for Batch 1 baseline forecasting and thermal risk engine."""

from datetime import datetime, timezone, timedelta
from app.intelligence.forecasting.baseline_model import PersistenceBaselineModel
from app.intelligence.thermal_risk.classification import classify_risk
from app.intelligence.thermal_risk.risk_engine import assess_thermal_risk
from app.intelligence.thermal_risk.thresholds import DEFAULT_DANGER_LIMIT_C, ELEVATED_MARGIN_C


def test_baseline_forecast_5_and_15_minute_horizons():
    """Verify that PersistenceBaselineModel produces 5-min and 15-min forecasts with mid, lo, hi."""
    model = PersistenceBaselineModel()
    now = datetime.now(timezone.utc)
    model.fit(temperature=75.0, timestamp=now, status="measured")

    pred5 = model.forecast("5")
    assert pred5["mid"] == 75.0
    assert pred5["lo"] == 74.0
    assert pred5["hi"] == 76.0
    assert pred5["trust"] == "high"

    pred15 = model.forecast("15")
    assert pred15["mid"] == 75.5
    assert pred15["lo"] == 73.5   # lo = latest - 1.5 = 75.0 - 1.5 = 73.5
    assert pred15["hi"] == 77.0   # hi = latest + 2.0 = 75.0 + 2.0 = 77.0
    assert pred15["trust"] == "high"


def test_confidence_band_validity_invariant():
    """Verify that lower confidence band <= midpoint <= upper confidence band for all temperatures."""
    model = PersistenceBaselineModel()
    now = datetime.now(timezone.utc)

    for temp in [20.0, 45.2, 78.0, 85.0, 95.5]:
        model.fit(temperature=temp, timestamp=now, status="measured")
        for horizon in ["5", "15"]:
            f = model.forecast(horizon)
            assert f["lo"] <= f["mid"] <= f["hi"], f"Failed invariant for temp={temp}, horizon={horizon}"


def test_stale_readings_produce_low_trust():
    """Verify that readings older than 5 minutes yield low trust."""
    model = PersistenceBaselineModel()
    # 6 minutes ago
    stale_time = datetime.now(timezone.utc) - timedelta(minutes=6)
    model.fit(temperature=70.0, timestamp=stale_time, status="measured")

    assert model.trust == "low"
    assert model.forecast("5")["trust"] == "low"
    assert model.forecast("15")["trust"] == "low"


def test_unavailable_and_estimated_sensor_status_handling():
    """Verify that unavailable and estimated sensor readings are handled honestly with low trust."""
    model = PersistenceBaselineModel()
    now = datetime.now(timezone.utc)

    # Unavailable sensor status
    model.fit(temperature=None, timestamp=now, status="unavailable")
    assert model.trust == "low"
    f_unavail = model.forecast("5")
    assert f_unavail["mid"] == 0.0
    assert f_unavail["trust"] == "low"

    # Estimated sensor status
    model.fit(temperature=65.0, timestamp=now, status="estimated")
    assert model.trust == "low"
    assert model.forecast("5")["trust"] == "low"


def test_thermal_risk_classification_rules():
    """Verify Normal, Elevated, and High classifications according to PRD B5."""
    limit = 85.0

    # 1. Normal: upper forecast < limit - 5 (i.e. < 80.0)
    assert classify_risk(hi_temp=79.5, limit_c=limit, current_temp=75.0) == "Normal"

    # 2. Elevated: upper forecast reaches limit - 5 (>= 80.0 and < 85.0)
    assert classify_risk(hi_temp=80.0, limit_c=limit, current_temp=75.0) == "Elevated"
    assert classify_risk(hi_temp=84.9, limit_c=limit, current_temp=75.0) == "Elevated"

    # 3. High: upper forecast reaches limit (>= 85.0)
    assert classify_risk(hi_temp=85.0, limit_c=limit, current_temp=75.0) == "High"
    assert classify_risk(hi_temp=92.5, limit_c=limit, current_temp=78.0) == "High"

    # 4. High if current temperature already exceeds limit
    assert classify_risk(hi_temp=82.0, limit_c=limit, current_temp=86.0) == "High"


def test_time_to_danger_calculation_in_risk_engine():
    """Verify that time to danger is calculated along the upper trajectory when in danger."""
    # Forecast matching PRD Page 2: now=78.0°C, 15m hi=92.5°C, limit=85°C
    forecast = {
        "5": {"mid": 82.1, "lo": 80.4, "hi": 84.0},
        "15": {"mid": 88.0, "lo": 84.0, "hi": 92.5},
    }
    result = assess_thermal_risk(forecast, current_temp=78.0, limit_c=85.0)
    assert result["risk"] == "High"
    # Rate = (92.5 - 78) / 15 = 14.5 / 15 = 0.9667 °C/min
    # Time to 85°C = (85 - 78) / 0.9667 = 7 / 0.9667 ≈ 7.24 min -> rounds to 7
    assert 7 <= result["time_to_danger_min"] <= 8

    # When current temp already >= limit, time to danger is 0
    at_danger = assess_thermal_risk(forecast, current_temp=86.0, limit_c=85.0)
    assert at_danger["risk"] == "High"
    assert at_danger["time_to_danger_min"] == 0

    # When risk is Normal, time to danger is 0
    normal_forecast = {
        "5": {"mid": 50.0, "lo": 49.0, "hi": 51.0},
        "15": {"mid": 50.5, "lo": 49.0, "hi": 52.5},
    }
    normal_res = assess_thermal_risk(normal_forecast, current_temp=50.0, limit_c=85.0)
    assert normal_res["risk"] == "Normal"
    assert normal_res["time_to_danger_min"] == 0


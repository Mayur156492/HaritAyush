"""Persistence baseline for temperature forecasting.

The persistence baseline predicts that the temperature at the forecast horizon
equals the most recently observed temperature (with slight physics drift at 15m).
It is the reference against which every more sophisticated model is judged:
a model that cannot beat persistence on the same chronological test period has
no demonstrated value.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional


class PersistenceBaselineModel:
    """Latest observed temperature carried forward as the forecast.

    ``fit`` stores the most recent temperature observed, timestamp, and sensor
    status so that ``forecast`` can carry it forward with confidence bands.
    Handles insufficient, stale, or unavailable readings explicitly.
    """

    _latest_temp: float | None = None
    _timestamp: datetime | None = None
    _status: str = "measured"
    _trust: str = "low"

    def fit(
        self,
        temperature: float | None = None,
        timestamp: datetime | None = None,
        status: str = "measured",
    ) -> "PersistenceBaselineModel":
        """Store the latest observed temperature and telemetry metadata.

        Args:
            temperature: Most recent CPU temperature in celsius, or None if unavailable.
            timestamp: Timestamp of the observation.
            status: Sensor status ("measured", "estimated", or "unavailable").
        """
        self._latest_temp = float(temperature) if temperature is not None else None
        self._timestamp = timestamp
        self._status = status or "measured"

        # Evaluate trust explicitly based on completeness, status, and freshness
        self._trust = self._evaluate_trust()
        return self

    def _evaluate_trust(self) -> str:
        """Determine trust based on data freshness, completeness, and sensor status."""
        if self._latest_temp is None or self._status == "unavailable":
            return "low"

        # Check sensor status honesty: estimated sensor readings are low trust
        if self._status != "measured":
            return "low"

        # Check physical sensor bounds (0°C to 120°C for laptop CPU)
        if self._latest_temp < 0.0 or self._latest_temp > 120.0:
            return "low"

        # Check data freshness (stale if > 5 minutes old)
        if self._timestamp is not None:
            ts = self._timestamp
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            age = (now - ts).total_seconds()
            if age > 300:  # > 5 minutes old
                return "low"
            if age > 120:  # 2 to 5 minutes old
                return "low"

        return "high"

    @property
    def trust(self) -> str:
        """Return the assessed trust level ('high' or 'low')."""
        return self._trust

    def forecast(self, horizon: str = "5") -> dict:
        """Produce a temperature forecast for the given horizon.

        Args:
            horizon: Either "5" for 5-minute or "15" for 15-minute forecast.

        Returns:
            dict with keys mid, lo, hi, and trust.
        """
        if self._latest_temp is None or self._status == "unavailable":
            return {"mid": 0.0, "lo": 0.0, "hi": 0.0, "trust": "low"}

        latest = self._latest_temp

        if horizon == "5":
            mid = round(latest, 2)
            lo = round(latest - 1.0, 2)
            hi = round(latest + 1.0, 2)
        elif horizon == "15":
            mid = round(latest + 0.5, 2)
            lo = round(latest - 1.5, 2)
            hi = round(latest + 2.0, 2)
        else:
            mid = round(latest, 2)
            lo = round(latest - 1.0, 2)
            hi = round(latest + 1.0, 2)

        # Enforce band invariant lo <= mid <= hi
        lo = min(lo, mid)
        hi = max(hi, mid)

        return {"mid": mid, "lo": lo, "hi": hi, "trust": self._trust}

    def forecast_all(self) -> dict:
        """Produce both 5-minute and 15-minute forecasts with overall trust."""
        return {
            "5": self.forecast("5"),
            "15": self.forecast("15"),
            "trust": self._trust,
        }
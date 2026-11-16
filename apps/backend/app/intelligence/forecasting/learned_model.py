"""Learned forecasting model for CPU temperature predictions.

Per HaritAyush specification:
- Provides separate 5-minute and 15-minute predictions.
- Uses actual historical observations at prediction time (no future data leakage).
- Uses timestamp-aware target construction with tolerance (does not assume consecutive rows are 5m/15m).
- Chronological train/evaluation validation.
- Safe fallback to persistence baseline when historical training data is insufficient.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Tuple, Optional, Dict, Any

import numpy as np
from sklearn.linear_model import Ridge

from app.models import Reading
from app.intelligence.forecasting.baseline_model import PersistenceBaselineModel

logger = logging.getLogger(__name__)

# Minimum number of valid supervised pairs required to train the learned model
MIN_TRAINING_PAIRS = 10
# Target horizons in seconds
HORIZON_5M_SEC = 300
HORIZON_15M_SEC = 900
# Tolerance window in seconds for matching future target observation (+/- 60s)
TIMESTAMP_TOLERANCE_SEC = 60


def _parse_ts(ts: datetime | str) -> datetime:
    if isinstance(ts, str):
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    else:
        dt = ts
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


class LearnedTemperatureModel:
    """Learned forecasting model predicting CPU temperature at 5m and 15m horizons."""

    def __init__(self, alpha: float = 1.0):
        self.alpha = alpha
        self.model_5m: Optional[Ridge] = None
        self.model_15m: Optional[Ridge] = None
        self.mae_5m: Optional[float] = None
        self.mae_15m: Optional[float] = None
        self.is_fitted: bool = False
        self.training_pairs_count: int = 0

    @staticmethod
    def extract_features(reading: Reading, prev_reading: Optional[Reading] = None) -> List[float]:
        """Extract features using only information available up to reading timestamp.

        Features:
        - cpu_temp_c (current)
        - cpu_pct (current)
        - mem_pct (current)
        - delta_temp (temp - prev_temp, if prev available within 60s, else 0.0)
        - delta_cpu (cpu - prev_cpu, if prev available within 60s, else 0.0)
        """
        temp = reading.cpu_temp_c if reading.cpu_temp_c is not None else 0.0
        cpu = reading.cpu_pct if reading.cpu_pct is not None else 0.0
        mem = reading.mem_pct if reading.mem_pct is not None else 0.0

        delta_temp = 0.0
        delta_cpu = 0.0
        if prev_reading is not None and prev_reading.cpu_temp_c is not None and prev_reading.cpu_pct is not None:
            t_curr = _parse_ts(reading.ts)
            t_prev = _parse_ts(prev_reading.ts)
            dt = (t_curr - t_prev).total_seconds()
            if 0 < dt <= 60:
                delta_temp = temp - prev_reading.cpu_temp_c
                delta_cpu = cpu - prev_reading.cpu_pct

        return [temp, cpu, mem, delta_temp, delta_cpu]

    def _build_dataset(
        self, readings: List[Reading], horizon_sec: int
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Construct (X, y) pairs matching each reading with an actual future reading.

        Strict rules:
        - Target must be at ts + horizon_sec (+/- TIMESTAMP_TOLERANCE_SEC).
        - Must have temp_status == 'measured' and cpu_temp_c is not None.
        - Only historical readings up to the query point are used for features.
        """
        X_list = []
        y_list = []

        valid_readings = [
            r for r in readings
            if r.cpu_temp_c is not None and r.temp_status == "measured" and r.ts is not None
        ]
        # Sort chronologically
        valid_readings.sort(key=lambda r: _parse_ts(r.ts))

        for i, r in enumerate(valid_readings):
            t_r = _parse_ts(r.ts)
            target_time = t_r + timedelta(seconds=horizon_sec)

            # Find matching future reading in [target_time - tol, target_time + tol]
            best_future = None
            best_diff = float("inf")

            for j in range(i + 1, len(valid_readings)):
                f_r = valid_readings[j]
                t_f = _parse_ts(f_r.ts)
                diff = abs((t_f - target_time).total_seconds())
                if diff <= TIMESTAMP_TOLERANCE_SEC and diff < best_diff:
                    best_diff = diff
                    best_future = f_r
                elif (t_f - target_time).total_seconds() > TIMESTAMP_TOLERANCE_SEC:
                    break

            if best_future is not None and best_future.cpu_temp_c is not None:
                prev_r = valid_readings[i - 1] if i > 0 else None
                feat = self.extract_features(r, prev_r)
                X_list.append(feat)
                y_list.append(best_future.cpu_temp_c)

        if not X_list:
            return np.empty((0, 5)), np.empty((0,))
        return np.array(X_list, dtype=np.float64), np.array(y_list, dtype=np.float64)

    def fit(self, readings: List[Reading]) -> bool:
        """Fit 5m and 15m models using chronological split validation.

        Returns True if model was successfully fitted, False otherwise.
        """
        X_5, y_5 = self._build_dataset(readings, HORIZON_5M_SEC)
        X_15, y_15 = self._build_dataset(readings, HORIZON_15M_SEC)

        if len(X_5) < MIN_TRAINING_PAIRS or len(X_15) < MIN_TRAINING_PAIRS:
            logger.info("Insufficient training pairs (%d, %d). Minimum required: %d", len(X_5), len(X_15), MIN_TRAINING_PAIRS)
            self.is_fitted = False
            return False

        # Chronological train/test split: 70% train, 30% validation
        split_5 = int(len(X_5) * 0.7)
        split_15 = int(len(X_15) * 0.7)

        # 5m model
        X_train_5, y_train_5 = X_5[:split_5], y_5[:split_5]
        X_val_5, y_val_5 = X_5[split_5:], y_5[split_5:]
        m5 = Ridge(alpha=self.alpha)
        m5.fit(X_train_5, y_train_5)
        if len(X_val_5) > 0:
            preds_val_5 = m5.predict(X_val_5)
            self.mae_5m = float(np.mean(np.abs(preds_val_5 - y_val_5)))
        else:
            self.mae_5m = None

        # 15m model
        X_train_15, y_train_15 = X_15[:split_15], y_15[:split_15]
        X_val_15, y_val_15 = X_15[split_15:], y_15[split_15:]
        m15 = Ridge(alpha=self.alpha)
        m15.fit(X_train_15, y_train_15)
        if len(X_val_15) > 0:
            preds_val_15 = m15.predict(X_val_15)
            self.mae_15m = float(np.mean(np.abs(preds_val_15 - y_val_15)))
        else:
            self.mae_15m = None

        # Refit on all historical data available
        m5.fit(X_5, y_5)
        m15.fit(X_15, y_15)

        self.model_5m = m5
        self.model_15m = m15
        self.training_pairs_count = min(len(X_5), len(X_15))
        self.is_fitted = True
        return True

    def predict(
        self,
        current_reading: Reading,
        prev_reading: Optional[Reading] = None,
    ) -> Optional[Dict[str, Any]]:
        """Predict 5m and 15m temperatures with confidence intervals.

        Returns None if not fitted or current reading is invalid.
        """
        if not self.is_fitted or self.model_5m is None or self.model_15m is None:
            return None
        if current_reading.cpu_temp_c is None or current_reading.temp_status != "measured":
            return None

        feat = np.array([self.extract_features(current_reading, prev_reading)], dtype=np.float64)
        pred_5 = float(self.model_5m.predict(feat)[0])
        pred_15 = float(self.model_15m.predict(feat)[0])

        # Bounds derived from empirical MAE or physical heuristics
        margin_5 = max(1.0, (self.mae_5m * 1.5) if self.mae_5m is not None else 1.5)
        margin_15 = max(2.0, (self.mae_15m * 1.5) if self.mae_15m is not None else 2.5)

        mid_5 = round(pred_5, 2)
        lo_5 = round(pred_5 - margin_5, 2)
        hi_5 = round(pred_5 + margin_5, 2)

        mid_15 = round(pred_15, 2)
        lo_15 = round(pred_15 - margin_15, 2)
        hi_15 = round(pred_15 + margin_15, 2)

        # Enforce physical constraints: temp must be >= 0 and <= 125
        mid_5 = max(0.0, min(125.0, mid_5))
        lo_5 = max(0.0, min(mid_5, lo_5))
        hi_5 = min(125.0, max(mid_5, hi_5))

        mid_15 = max(0.0, min(125.0, mid_15))
        lo_15 = max(0.0, min(mid_15, lo_15))
        hi_15 = min(125.0, max(mid_15, hi_15))

        # Trust evaluation
        trust = "high"
        if self.mae_5m is not None and self.mae_5m > 3.0:
            trust = "low"
        if self.training_pairs_count < 20:
            trust = "low"

        return {
            "5": {"mid": mid_5, "lo": lo_5, "hi": hi_5, "trust": trust},
            "15": {"mid": mid_15, "lo": lo_15, "hi": hi_15, "trust": trust},
            "trust": trust,
            "source": "learned_ridge",
            "training_pairs": self.training_pairs_count,
            "mae_5m": self.mae_5m,
            "mae_15m": self.mae_15m,
        }


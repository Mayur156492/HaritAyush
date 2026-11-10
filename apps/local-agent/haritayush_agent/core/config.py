from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    backend_url: str = "http://127.0.0.1:8000"
    site_id: str = "laptop-01"
    interval_s: float = 3.0
    request_timeout_s: float = 2.0
    cap_min_pct: int = 30
    cap_max_pct: int = 80
    action_timeout_s: float = 60.0
    cooldown_s: float = 30.0
    settle_s: float = 45.0
    temperature_rise_rollback_c: float = 2.0
    state_dir: Path = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "HaritAyush" / "agent"

    def __post_init__(self) -> None:
        if not self.backend_url.startswith(("http://", "https://")):
            raise ValueError("backend_url must use http:// or https://")
        if not self.site_id.strip():
            raise ValueError("site_id must not be empty")
        if not 2.0 <= self.interval_s <= 5.0:
            raise ValueError("interval_s must be between 2 and 5 seconds")
        if not 0.2 <= self.request_timeout_s <= 10:
            raise ValueError("request_timeout_s must be between 0.2 and 10 seconds")
        if not (1 <= self.cap_min_pct < self.cap_max_pct <= 100):
            raise ValueError("cap bounds must satisfy 1 <= cap_min_pct < cap_max_pct <= 100")
        if not 10 <= self.action_timeout_s <= 3600:
            raise ValueError("action_timeout_s must be between 10 and 3600 seconds")
        if not 0 <= self.cooldown_s <= 3600:
            raise ValueError("cooldown_s must be between 0 and 3600 seconds")
        if not 30 <= self.settle_s <= 60:
            raise ValueError("settle_s must be between 30 and 60 seconds")
        if not 0 < self.temperature_rise_rollback_c <= 20:
            raise ValueError("temperature rise rollback threshold must be between 0 and 20 C")

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            backend_url=os.environ.get("HARITAYUSH_BACKEND_URL", cls.backend_url).rstrip("/"),
            site_id=os.environ.get("HARITAYUSH_SITE_ID", "laptop-01"),
            interval_s=_bounded_float("HARITAYUSH_INTERVAL_S", 3.0, 2.0, 5.0),
            request_timeout_s=_bounded_float("HARITAYUSH_REQUEST_TIMEOUT_S", 2.0, 0.2, 10.0),
            cap_min_pct=_bounded_int("HARITAYUSH_CAP_MIN_PCT", 30, 1, 99),
            cap_max_pct=_bounded_int("HARITAYUSH_CAP_MAX_PCT", 80, 2, 100),
            action_timeout_s=_bounded_float("HARITAYUSH_ACTION_TIMEOUT_S", 60.0, 10.0, 3600.0),
            temperature_rise_rollback_c=_bounded_float("HARITAYUSH_TEMP_RISE_ROLLBACK_C", 2.0, 0.1, 20.0),
            cooldown_s=_bounded_float("HARITAYUSH_COOLDOWN_S", 30.0, 0.0, 3600.0),
            settle_s=_bounded_float("HARITAYUSH_SETTLE_S", 45.0, 30.0, 60.0),
            state_dir=Path(os.environ.get("HARITAYUSH_STATE_DIR", str(cls.state_dir))).expanduser(),
        )


def _bounded_float(name: str, default: float, low: float, high: float) -> float:
    try:
        value = float(os.environ.get(name, default))
    except ValueError as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not low <= value <= high:
        raise ValueError(f"{name} must be between {low} and {high}")
    return value


def _bounded_int(name: str, default: int, low: int, high: int) -> int:
    raw = os.environ.get(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not low <= value <= high:
        raise ValueError(f"{name} must be between {low} and {high}")
    return value

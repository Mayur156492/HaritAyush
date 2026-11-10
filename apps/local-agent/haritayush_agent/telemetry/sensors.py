from __future__ import annotations

import json
import logging
import math
import platform
import subprocess
import threading
import time
from dataclasses import dataclass

import psutil

log = logging.getLogger(__name__)
UNAVAILABLE_SENSORS = ["gpu_temp", "fan_rpm", "inlet_temp", "humidity", "power_w"]
POWERSHELL_TIMEOUT_S = 4.0


@dataclass(frozen=True)
class TemperatureSensor:
    provider: str
    name: str
    value_c: float | None
    raw_value: str


@dataclass(frozen=True)
class TemperatureDiscovery:
    sensors: tuple[TemperatureSensor, ...]
    detail: str


@dataclass(frozen=True)
class Reading:
    taken_monotonic: float
    payload: dict
    temperature_sensors: tuple[TemperatureSensor, ...] = ()
    selected_temperature_sensor: TemperatureSensor | None = None
    temperature_detail: str = ""


_SENSOR_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
$found = [System.Collections.Generic.List[object]]::new()
$problems = [System.Collections.Generic.List[string]]::new()
foreach ($ns in @('root/LibreHardwareMonitor', 'root/OpenHardwareMonitor')) {
  try {
    $items = Get-CimInstance -Namespace $ns -ClassName Sensor -Filter "SensorType='Temperature'"
    foreach ($item in $items) {
      $formattedValue = ([double]$item.Value).ToString([cultureinfo]::InvariantCulture)
      $found.Add(@{ provider=$ns; name=[string]$item.Name; value=$formattedValue })
    }
  } catch {
    $problems.Add("$ns : $($_.Exception.Message)")
  }
}
@{ sensors=@($found.ToArray()); errors=@($problems.ToArray()) } | ConvertTo-Json -Depth 4 -Compress
"""


def discover_temperature_sensors() -> TemperatureDiscovery:
    """Return actual WMI temperature sensors; retry one timed-out query once."""
    if platform.system() != "Windows":
        return TemperatureDiscovery((), "WMI sensor discovery is available only on Windows")

    last_error = ""
    for attempt in (1, 2):
        try:
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", _SENSOR_SCRIPT],
                capture_output=True, text=True, timeout=POWERSHELL_TIMEOUT_S, check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except subprocess.TimeoutExpired:
            last_error = f"PowerShell temperature query timed out after {POWERSHELL_TIMEOUT_S:g}s"
            log.warning("%s (attempt %s/2)", last_error, attempt)
            if attempt == 1:
                continue
            return TemperatureDiscovery((), f"{last_error}; retry also timed out")
        except OSError as exc:
            return TemperatureDiscovery((), f"Could not start PowerShell sensor query: {exc}")

        if result.returncode != 0:
            detail = result.stderr.strip() or f"PowerShell exited with code {result.returncode}"
            return TemperatureDiscovery((), detail)
        try:
            decoded = json.loads(result.stdout)
            records = decoded.get("sensors", []) if isinstance(decoded, dict) else []
            errors = decoded.get("errors", []) if isinstance(decoded, dict) else []
        except (json.JSONDecodeError, AttributeError):
            return TemperatureDiscovery((), "PowerShell returned sensor data that could not be parsed")

        sensors: list[TemperatureSensor] = []
        if isinstance(records, dict):
            records = [records]
        for item in records if isinstance(records, list) else []:
            if not isinstance(item, dict):
                continue
            raw = str(item.get("value", "")).strip()
            try:
                value = float(raw)
                if not math.isfinite(value) or not 0 <= value <= 120:
                    value = None
            except ValueError:
                value = None
            sensors.append(TemperatureSensor(
                provider=str(item.get("provider", "unknown")),
                name=str(item.get("name", "(unnamed sensor)")),
                value_c=value,
                raw_value=raw,
            ))
        detail = "; ".join(str(error) for error in errors if error) or "Both WMI providers queried"
        return TemperatureDiscovery(tuple(sensors), detail)
    return TemperatureDiscovery((), last_error or "No temperature sensor data returned")


def is_cpu_temperature_sensor(name: str) -> bool:
    """Match CPU-only thermal names while explicitly excluding GPU/non-CPU sensors."""
    normalized = name.casefold()
    excluded = ("gpu", "graphics", "vram", "video memory", "nvidia", "radeon", "hotspot", "non-cpu")
    if any(marker in normalized for marker in excluded):
        return False
    import re
    return bool(
        re.search(r"\bcpu\b", normalized)
        or re.search(r"\bprocessor\b", normalized)
        or re.search(r"\btctl\b|\btdie\b", normalized)
        or (re.search(r"\bcore\s*#?\s*\d+\b", normalized)
            and ("cpu" in normalized or "processor" in normalized))
    )


def select_cpu_temperature_sensor(discovery: TemperatureDiscovery) -> tuple[TemperatureSensor | None, str]:
    cpu_sensors = [sensor for sensor in discovery.sensors if is_cpu_temperature_sensor(sensor.name)]
    readable = [sensor for sensor in cpu_sensors if sensor.value_c is not None]
    if readable:
        # Using the hottest real CPU sensor is conservative for rollback decisions.
        return max(readable, key=lambda sensor: sensor.value_c or 0.0), "selected the hottest readable CPU temperature sensor"
    if cpu_sensors:
        return None, "CPU temperature sensor(s) matched by name, but their values were unreadable or outside 0-120 C"
    if discovery.sensors:
        return None, "temperature sensors were found, but none had a CPU-specific name; GPU and non-CPU sensors are ignored"
    return None, f"no LHM/OHM temperature sensors were returned ({discovery.detail})"


def format_temperature_sensors(discovery: TemperatureDiscovery) -> list[str]:
    if not discovery.sensors:
        return [f"  No temperature sensors found: {discovery.detail}"]
    lines = []
    for sensor in discovery.sensors:
        value = f"{sensor.value_c:.1f} C" if sensor.value_c is not None else f"unreadable (raw={sensor.raw_value!r})"
        lines.append(f"  {sensor.provider}: {sensor.name} = {value}")
    return lines


def _read_cpu_temperature() -> float | None:
    """Read one fresh real CPU sensor value; never retain a previous sample."""
    sensor, _ = select_cpu_temperature_sensor(discover_temperature_sensors())
    return sensor.value_c if sensor is not None else None


class SensorReader:
    def __init__(self, site_id: str = "laptop-01") -> None:
        self.site_id = site_id
        self._lock = threading.Lock()
        psutil.cpu_percent(interval=None)  # prime psutil's nonblocking CPU sampler

    def read(self, *, job_running: bool, cap_pct: int) -> Reading:
        with self._lock:
            return self._read_locked(job_running=job_running, cap_pct=cap_pct)

    def _read_locked(self, *, job_running: bool, cap_pct: int) -> Reading:
        cpu = psutil.cpu_percent(interval=None)
        memory = psutil.virtual_memory().percent
        discovery = discover_temperature_sensors()
        selected, detail = select_cpu_temperature_sensor(discovery)
        temp = selected.value_c if selected is not None else None
        unavailable = list(UNAVAILABLE_SENSORS)
        if temp is None:
            unavailable.append("cpu_temp")
        payload = {
            "site_id": self.site_id,
            "ts": _utc_now(),
            "cpu_pct": round(min(100.0, max(0.0, cpu)), 1),
            "mem_pct": round(min(100.0, max(0.0, memory)), 1),
            "cpu_temp_c": round(temp, 1) if temp is not None else None,
            "temp_status": "measured" if temp is not None else "unavailable",
            "unavailable": unavailable,
            "demo_job": {"running": job_running, "cap_pct": cap_pct if job_running else 100},
        }
        return Reading(time.monotonic(), payload, discovery.sensors, selected, detail)


class SimulatedSensorReader(SensorReader):
    """DEV ONLY: real CPU/memory load plus a synthetic, always-estimated temperature."""

    is_simulated = True

    def read(self, *, job_running: bool, cap_pct: int) -> Reading:
        with self._lock:
            cpu = psutil.cpu_percent(interval=None)
            memory = psutil.virtual_memory().percent
            if not job_running:
                temperature = 48.0
            elif cap_pct < 100:
                temperature = 56.0
            else:
                temperature = 62.0
            payload = {
                "site_id": self.site_id,
                "ts": _utc_now(),
                "cpu_pct": round(min(100.0, max(0.0, cpu)), 1),
                "mem_pct": round(min(100.0, max(0.0, memory)), 1),
                "cpu_temp_c": temperature,
                "temp_status": "estimated",
                "unavailable": list(UNAVAILABLE_SENSORS),
                "demo_job": {"running": job_running, "cap_pct": cap_pct if job_running else 100},
            }
            return Reading(time.monotonic(), payload, temperature_detail="DEV simulation (not a hardware sensor)")


def _utc_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

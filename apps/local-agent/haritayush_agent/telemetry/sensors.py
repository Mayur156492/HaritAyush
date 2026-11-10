from __future__ import annotations

import platform
import subprocess
import threading
import time
from dataclasses import dataclass

import psutil

UNAVAILABLE_SENSORS = ["gpu_temp", "fan_rpm", "inlet_temp", "humidity", "power_w"]


@dataclass(frozen=True)
class Reading:
    taken_monotonic: float
    payload: dict


def _read_cpu_temperature() -> float | None:
    """Read only a Windows-reported thermal sensor. No load-based estimates."""
    if platform.system() != "Windows":
        return None
    # ACPI thermal zones are frequently absent or fixed at a meaningless value.
    # LibreHardwareMonitor and OpenHardwareMonitor expose actual CPU sensors via WMI.
    script = (
        "$ErrorActionPreference='Stop'; "
        "foreach ($ns in @('root/LibreHardwareMonitor','root/OpenHardwareMonitor')) { "
        "try { $s=Get-CimInstance -Namespace $ns -ClassName Sensor "
        "-Filter \"SensorType='Temperature'\" | Where-Object {$_.Name -match 'CPU Package|CPU Die|CPU CCD.*Tdie|Core Max|Core \\(Tctl/Tdie\\)'} "
        "| Select-Object -First 1 -ExpandProperty Value; "
        "if ($null -ne $s) { [Console]::Write([string]$s); break } } catch {} }"
    )
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=1.5, check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        value = float(result.stdout.strip()) if result.returncode == 0 and result.stdout.strip() else None
        return value if value is not None and 0.0 <= value <= 120.0 else None
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None


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
        temp = _read_cpu_temperature()
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
        return Reading(time.monotonic(), payload)


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
            return Reading(time.monotonic(), payload)


def _utc_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

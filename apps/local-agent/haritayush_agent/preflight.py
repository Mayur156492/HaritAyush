"""Real, non-simulated Windows readiness checks for the local agent."""

from __future__ import annotations

import ctypes
import platform
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Callable

from haritayush_agent.communication.client import BackendClient
from haritayush_agent.core.config import Settings
from haritayush_agent.telemetry.sensors import SensorReader, format_temperature_sensors
from haritayush_agent.workload.demo_job import WindowsJob


def _is_administrator() -> bool:
    if platform.system() != "Windows":
        return False
    return bool(ctypes.windll.shell32.IsUserAnAdmin())


def _check_job_object() -> str:
    if platform.system() != "Windows":
        raise RuntimeError("Windows Job Objects are only available on Windows")
    job = None
    child = None
    try:
        # Sleeping is harmless; it performs no file, network, or system changes.
        job = WindowsJob(worker_count=1)
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"],
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, close_fds=True)
        deadline = time.monotonic() + 5
        while child.poll() is None and time.monotonic() < deadline:
            try:
                job.assign(child.pid)
                break
            except OSError:
                time.sleep(0.05)
        else:
            raise RuntimeError("could not assign the harmless child process to the Job Object")
        job.cap(50)
        job.cap(100)  # 100% removes the test cap; closing the Job Object below cleans up.
        return "created Job Object, set a 50% CPU limit, restored 100%, and closed it"
    finally:
        if job is not None:
            job.close()
        if child is not None and child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=3)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=2)


def _check_kill_switch(state_dir: Path) -> str:
    state_dir.mkdir(parents=True, exist_ok=True)
    probe = None
    try:
        with tempfile.NamedTemporaryFile(prefix=".preflight-", dir=state_dir, delete=False) as handle:
            probe = Path(handle.name)
            handle.write(b"writable")
        probe.unlink()
    finally:
        if probe is not None and probe.exists():
            probe.unlink()
    return f"stop file is watched at {state_dir / 'KILL'}; directory is writable"


def _report(name: str, check: Callable[[], str], hint: str) -> bool:
    try:
        detail = check()
        print(f"PASS - {name}: {detail}")
        return True
    except Exception as exc:
        print(f"FAIL - {name}: {exc}\n  Fix: {hint}")
        return False


def run_preflight(settings: Settings) -> int:
    """Run all requested checks and return 0 only when every check passes."""
    print("HaritAyush Windows agent preflight (real readings only; no simulated data)")
    outcomes: list[bool] = []
    outcomes.append(_report(
        "1. Administrator privileges",
        lambda: "running elevated" if _is_administrator() else _raise("not running as Administrator"),
        "Open PowerShell with Run as administrator, then run this command again.",
    ))

    sensor_reader = SensorReader(settings.site_id)
    reading = None

    def check_temperature() -> str:
        nonlocal reading
        sample = sensor_reader.read(job_running=False, cap_pct=100)
        reading = sample.payload
        print("  Temperature sensors found:")
        from haritayush_agent.telemetry.sensors import TemperatureDiscovery, select_cpu_temperature_sensor
        inventory = TemperatureDiscovery(sample.temperature_sensors, sample.temperature_detail)
        for line in format_temperature_sensors(inventory):
            print(line)
        selected, explanation = select_cpu_temperature_sensor(inventory)
        if selected is None or reading["temp_status"] != "measured" or reading["cpu_temp_c"] is None:
            print(f"  Agent picked: none. {explanation}.")
            raise RuntimeError(explanation)
        print(f"  Agent picked: {selected.provider}: {selected.name} = {selected.value_c:.1f} C")
        return f"{selected.provider} reachable; selected {selected.name} at {selected.value_c:.1f} C (measured)"

    outcomes.append(_report(
        "2. Hardware monitor and real CPU temperature", check_temperature,
        "Install and start LibreHardwareMonitor or OpenHardwareMonitor as Administrator; enable WMI, then confirm a CPU Package/Die sensor appears.",
    ))

    def check_cpu_memory() -> str:
        nonlocal reading
        reading = sensor_reader.read(job_running=False, cap_pct=100).payload
        cpu, memory = reading["cpu_pct"], reading["mem_pct"]
        if not (isinstance(cpu, (int, float)) and 0 <= cpu <= 100
                and isinstance(memory, (int, float)) and 0 <= memory <= 100):
            raise RuntimeError("CPU or memory reading was missing or outside 0-100")
        return f"CPU {cpu:.1f}%; memory {memory:.1f}%"

    outcomes.append(_report(
        "3. CPU and memory readings", check_cpu_memory,
        "Reinstall the agent dependencies with .\\.venv\\Scripts\\python.exe -m pip install -e .; check Windows Performance Counters and available memory.",
    ))

    def check_backend() -> str:
        nonlocal reading
        client = BackendClient(settings.backend_url, settings.request_timeout_s)
        health_status, _ = client.request("GET", "/health")
        if health_status != 200:
            raise RuntimeError(f"GET /health returned HTTP {health_status}, expected 200")
        if reading is None:
            reading = sensor_reader.read(job_running=False, cap_pct=100).payload
        status, _ = client.request("POST", "/readings", reading, f"preflight:{uuid.uuid4()}")
        if status != 201:
            raise RuntimeError(f"POST /readings returned HTTP {status}, expected 201")
        return f"{settings.backend_url} GET /health=200; POST /readings=201 (live CPU/memory and actual sensor status)"

    outcomes.append(_report(
        "4. Backend health and real-reading upload", check_backend,
        "Start the backend, set HARITAYUSH_BACKEND_URL to its base URL, and confirm it implements GET /health and POST /readings with HTTP 201.",
    ))
    outcomes.append(_report(
        "5. Windows Job Object CPU limit", _check_job_object,
        "Use supported Windows 10/11, close restrictive endpoint policies, and rerun PowerShell as Administrator. Check Windows API access if it still fails.",
    ))
    outcomes.append(_report(
        "6. Local kill switch", lambda: _check_kill_switch(settings.state_dir),
        "Allow the agent account to write to the configured state directory; the agent watches the KILL file there.",
    ))

    passed = sum(outcomes)
    print(f"Preflight result: {passed}/{len(outcomes)} checks passed")
    return 0 if all(outcomes) else 1


def _raise(message: str):
    raise RuntimeError(message)

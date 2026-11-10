from __future__ import annotations

import argparse
import logging
import platform
import sys

from haritayush_agent.core.agent import Agent
from haritayush_agent.core.config import Settings


def main() -> int:
    parser = argparse.ArgumentParser(description="HaritAyush Windows telemetry and safe CPU-cap agent")
    parser.add_argument("--check", action="store_true", help="check dependencies, OS, configuration and sensor visibility")
    parser.add_argument("preflight", nargs="?", choices=("preflight",), help="run six real Windows readiness checks")
    parser.add_argument("--dev-mock", action="store_true", help="DEV ONLY: use estimated simulated temperature and a state-only demo job")
    parser.add_argument("--dev-allow-estimated-cap", action="store_true",
                        help="TEST ONLY: let the simulated job accept estimated temperature; never enables a real OS cap")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = Settings.from_env()
    if args.dev_allow_estimated_cap and not args.dev_mock:
        parser.error("--dev-allow-estimated-cap requires --dev-mock")
    if args.preflight == "preflight":
        from haritayush_agent.preflight import run_preflight
        return run_preflight(settings)
    if platform.system() != "Windows" and not args.dev_mock:
        print("HaritAyush local agent requires Windows 10/11; telemetry preview is not enabled on other platforms.", file=sys.stderr)
        return 2
    if args.check:
        from haritayush_agent.telemetry.sensors import (
            SensorReader, SimulatedSensorReader, TemperatureDiscovery,
            discover_temperature_sensors, format_temperature_sensors,
            select_cpu_temperature_sensor,
        )
        reader = SimulatedSensorReader if args.dev_mock else SensorReader
        if args.dev_mock:
            print("*** DEV ONLY: CPU temperature source is simulated, status=estimated; never measured. ***", file=sys.stderr)
        if args.dev_allow_estimated_cap:
            print("*** LOUD WARNING: TEST OVERRIDE ON; state-only workload, no real OS cap possible. ***", file=sys.stderr)
        reading = reader(settings.site_id).read(job_running=False, cap_pct=100)
        discovery = (TemperatureDiscovery(reading.temperature_sensors, reading.temperature_detail)
                     if not args.dev_mock else discover_temperature_sensors())
        selected, selection_detail = select_cpu_temperature_sensor(discovery)
        print(f"Windows: {platform.version()}\nBackend: {settings.backend_url}\nState directory: {settings.state_dir}\n"
              f"CPU: {reading.payload['cpu_pct']}%  Memory: {reading.payload['mem_pct']}%\n"
              f"CPU temperature: {reading.payload['cpu_temp_c']} ({reading.payload['temp_status']})\n"
              "Temperature sensors found:")
        print("\n".join(format_temperature_sensors(discovery)))
        if args.dev_mock:
            print("Agent picked: DEV simulated temperature (estimated; not a hardware sensor)")
        elif selected:
            print(f"Agent picked: {selected.provider}: {selected.name} = {selected.value_c:.1f} C")
        else:
            print(f"Agent picked: none. {selection_detail}.")
        print(f"Unavailable sensors: {', '.join(reading.payload['unavailable'])}\n"
              f"Safety thresholds: action_timeout_s={settings.action_timeout_s:.1f}; "
              f"temperature_rise_rollback_c={settings.temperature_rise_rollback_c:.1f} C")
        return 0
    agent = Agent(settings, dev_mock=args.dev_mock,
                  allow_estimated_for_tests=args.dev_allow_estimated_cap)
    try:
        agent.run()
    except KeyboardInterrupt:
        logging.info("Shutdown requested")
    finally:
        agent.stop()
        agent.outbox.db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

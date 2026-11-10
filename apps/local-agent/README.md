# HaritAyush Windows agent

This package implements Person 2's module for Windows 10/11 and the frozen v1 API contract.

## Install and run

Use Python 3.11 or newer on Windows. From this directory in PowerShell:

```powershell
.\scripts\install.ps1
$env:HARITAYUSH_BACKEND_URL = "http://127.0.0.1:8000"
.\.venv\Scripts\haritayush-agent.exe preflight
.\scripts\run.ps1
```

Preflight checks administrator access, a real LHM/OHM CPU temperature, CPU/memory readings, backend health and reading upload, a harmless child-process Job Object cap, and the local stop-file directory. See [WINDOWS_RUNBOOK.md](WINDOWS_RUNBOOK.md) for exact setup steps. Preflight sends one real reading to the configured backend.

For another backend machine, set `HARITAYUSH_BACKEND_URL` to its reachable URL. The prototype API has no authentication; keep an HTTP deployment on a trusted network. `https://` URLs are supported by the standard library client.

## Safety and honesty

- Readings use UTC ISO 8601 timestamps, the configured site ID (default `laptop-01`), and exactly the contract's fields.
- CPU and memory come from `psutil`. CPU temperature is reported as `measured` only when the LibreHardwareMonitor or OpenHardwareMonitor WMI provider exposes CPU package/die/core temperature. Install and run one of these providers and enable its WMI interface if the laptop supports it. Otherwise `cpu_temp_c` is `null`, `temp_status` is `unavailable`, and `cpu_temp` appears in `unavailable`. No temperature is inferred from CPU load.
- GPU temperature, fan speed, inlet temperature, humidity, and power are listed unavailable because this agent does not collect them. Whether a particular laptop physically exposes them must be checked on that laptop.
- The demo stress workers are two separate children (or one on a single-core host), assigned to their own Windows Job Object. CPU caps apply only to that bounded worker pool, within the configured range (30-80% by default), scaled to its logical CPU allocation so the cap is effective on multi-core laptops. A Job Object kill-on-close limit terminates the demo workers if the agent exits unexpectedly.
- `cpu_cap` requires `action_id`, `approved_by`, `approved_at`, a running demo job, an in-bounds cap, a measured temperature less than 10 seconds old, no other active cap, passed cooldown, and an inactive kill switch. Failures are audited and do not apply anything.
- The cap is removed after the configured timeout, if measured temperature rises by 2 C, on `stop_job`, or with the local kill switch. The agent logs before/after data after the settle interval.
- A durable SQLite outbox buffers readings and audit entries through backend outages in one ordered stream. Command IDs are persisted before processing to prevent duplicate application. The local `KILL` file at `%LOCALAPPDATA%\HaritAyush\agent\KILL` is checked every loop; create it to stop the workload and prevent further actions for that run. Restart the agent to re-arm it.
- Sensor sampling runs independently from network retries, so a slow backend does not stall the 2-5 second sampling cadence. Outbox sends use stable idempotency keys; backends should honor the `Idempotency-Key` HTTP header to suppress retry duplicates.

## Configuration

| Variable | Default | Bounds / use |
|---|---|---|
| `HARITAYUSH_BACKEND_URL` | `http://127.0.0.1:8000` | Backend base URL |
| `HARITAYUSH_SITE_ID` | `laptop-01` | Site ID sent in readings and audit events |
| `HARITAYUSH_INTERVAL_S` | `3` | 2-5 seconds |
| `HARITAYUSH_REQUEST_TIMEOUT_S` | `2` | 0.2-10 seconds |
| `HARITAYUSH_CAP_MIN_PCT` | `30` | 1-99; must be below max |
| `HARITAYUSH_CAP_MAX_PCT` | `80` | 2-100; must be above min |
| `HARITAYUSH_ACTION_TIMEOUT_S` | `60` | 10-3600 seconds |
| `HARITAYUSH_TEMP_RISE_ROLLBACK_C` | `2.0` | 0.1-20 C; roll back if the selected CPU sensor rises by this amount |
| `HARITAYUSH_COOLDOWN_S` | `30` | 0-3600 seconds |
| `HARITAYUSH_SETTLE_S` | `45` | 30-60 seconds |
| `HARITAYUSH_STATE_DIR` | `%LOCALAPPDATA%\HaritAyush\agent` | Local SQLite outbox and kill file |

The production backend must implement `POST /readings`, `GET /commands/pending?site_id=...`, and `POST /audit` as specified in `HaritAyush_API_Contract.md`. This repository has a DEV-only mock, but no production backend routes yet.

The cap bounds are local agent settings (30-80% by default), independent of backend commands; the backend cannot widen them. Create `%LOCALAPPDATA%\HaritAyush\agent\KILL` to invoke the local kill switch.

At startup, the agent prints the active action timeout and temperature-rise rollback threshold. `--check` and `preflight` list all values returned by the LHM/OHM temperature providers and identify the selected CPU sensor. GPU and other non-CPU names are never eligible. Temperature queries have a 4-second timeout, one logged timeout retry, and no cached-value fallback.

## DEV-only Mac mock

`haritayush_agent.mock_backend` provides an in-memory API mock on port 8001. Its `/dev/commands` endpoint is only a test helper. The simulated sensor reports `temp_status: estimated`; it never reports a simulated value as measured. The state-only demo job cannot create a process or apply an OS cap. `--dev-allow-estimated-cap` prints a loud warning and only enables the simulated job's in-memory cap for tests.

```sh
cd apps/local-agent
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
python -m haritayush_agent.mock_backend --host 127.0.0.1 --port 8001
```

In another terminal, run the dev agent and submit presenter commands:

```sh
cd apps/local-agent
. .venv/bin/activate
HARITAYUSH_BACKEND_URL=http://127.0.0.1:8001 python -m haritayush_agent --dev-mock --dev-allow-estimated-cap
curl -X POST http://127.0.0.1:8001/dev/commands -H 'Content-Type: application/json' -d '{"type":"start_job"}'
curl -X POST http://127.0.0.1:8001/dev/commands -H 'Content-Type: application/json' -d '{"type":"cpu_cap","cap_pct":50,"action_id":"a-dev","approved_by":"Dev operator","approved_at":"2026-11-10T10:00:00Z"}'
```

The end-to-end test starts/stops its own mock backend and agent, including the 30-second minimum settle interval and an accelerated test rollback timer:

```sh
cd apps/local-agent
. .venv/bin/activate
python -m unittest discover -s tests -p 'test_mock_backend_e2e.py' -v
```

## Limitations

This is a prototype controller for a deliberately isolated demonstration workload. Windows Job Object CPU rate control limits the demo process's CPU time; it is not a hardware thermal governor and does not cap system-wide CPU. CPU temperature support depends on the laptop firmware and sensor provider. If measured CPU temperature is unavailable, the agent intentionally refuses CPU-cap actions under the shared five-check policy.

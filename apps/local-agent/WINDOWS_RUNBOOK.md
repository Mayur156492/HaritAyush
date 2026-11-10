# Windows runbook

## 1. Install the agent

Install Python 3.11 or newer and Git. Open PowerShell and run:

```powershell
git clone https://github.com/Mayur156492/HaritAyush.git
cd HaritAyush\apps\local-agent
.\scripts\install.ps1
```

## 2. Start a real temperature monitor

Install and start **LibreHardwareMonitor** or **OpenHardwareMonitor**. Run the monitor as Administrator and enable its WMI interface. Check that it shows a CPU Package, CPU Die, or CPU Core temperature. The agent never invents a temperature; without a real sensor it reports temperature as unavailable and will not apply a cap.

## 3. Set the backend address

Use the URL of the deployed HaritAyush backend. Do not use the development mock for real operation.

```powershell
$env:HARITAYUSH_BACKEND_URL = "https://YOUR-BACKEND-HOST"
```

The backend must provide `GET /health`, `POST /readings`, `GET /commands/pending`, and `POST /audit`.

## 4. Run preflight as Administrator

Open **PowerShell as Administrator**, change to `HaritAyush\apps\local-agent`, set the backend address again in that window, and run:

```powershell
.\.venv\Scripts\haritayush-agent.exe preflight
```

Fix each `FAIL` using its printed hint, then rerun preflight. All six checks must say `PASS` before starting the agent. The backend check sends one real CPU/memory reading and the real sensor status to `POST /readings`.

## 5. Start and stop the agent

Start it in the same Administrator PowerShell window:

```powershell
.\scripts\run.ps1
```

To stop safely, press `Ctrl+C`. For the local emergency stop, create the `KILL` file in the agent state directory shown at startup. The default directory is `%LOCALAPPDATA%\HaritAyush\agent`:

```powershell
New-Item -ItemType File -Force "$env:LOCALAPPDATA\HaritAyush\agent\KILL"
```

The agent removes the demo job's cap, stops its own demo workload, logs `kill_switch`, and halts further actions. Delete a leftover `KILL` file only when you are ready to start the agent again.

## 6. Verify operation

The console shows agent status and warnings. Check the backend's audit view for `job_started`, `action_applied`, `action_result`, `rolled_back`, and `kill_switch` events. A cap is accepted only with approval, a fresh measured CPU temperature, a valid configured cap, the agent-owned demo job, and no active action or cooldown.

$ErrorActionPreference = "Stop"

if ($env:OS -ne "Windows_NT") {
    throw "HaritAyush local agent requires Windows 10/11."
}

$Python = Get-Command py -ErrorAction SilentlyContinue
if (-not $Python) {
    throw "Python 3.11 or newer is required. Install it from python.org, then rerun this script."
}

py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"
if ($LASTEXITCODE -ne 0) { throw "Python 3.11 or newer is required." }
py -3 -m venv .venv
if ($LASTEXITCODE -ne 0) { throw "Could not create the Python virtual environment." }
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "Could not update pip." }
& .\.venv\Scripts\python.exe -m pip install .
if ($LASTEXITCODE -ne 0) { throw "Could not install HaritAyush agent dependencies." }

Write-Host "Installed. Configure HARITAYUSH_BACKEND_URL, then run PowerShell as Administrator and use: .\.venv\Scripts\haritayush-agent.exe preflight"

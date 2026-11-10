$ErrorActionPreference = "Stop"
if (-not (Test-Path ".\.venv\Scripts\haritayush-agent.exe")) {
    throw "Agent not installed. Run .\scripts\install.ps1 first."
}
& .\.venv\Scripts\haritayush-agent.exe @args

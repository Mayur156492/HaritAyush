# HaritAyush
HaritAyush is a distributed thermal intelligence platform that uses real-time hardware monitoring, AI-powered temperature forecasting, thermal risk assessment and intelligent workload management to prevent overheating, optimize computing resources and promote energy-efficient digital infrastructure.

## Person 2: Windows local agent

The agent implementation and Windows setup are in [`apps/local-agent`](apps/local-agent/README.md). It publishes CPU and memory usage every 3 seconds, reports CPU temperature only when a real Windows sensor is available, and handles the isolated demo workload, approved CPU caps, local kill switch, rollback and audit/outbox delivery.

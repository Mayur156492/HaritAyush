# THERMOS
## Thermal Heuristic Engine for Reasoning, Monitoring, Optimisation and Safety

**Predict. Reason. Protect.**

THERMOS is an AI-powered predictive and autonomous thermal management architecture for data centres. It combines machine learning, spatial-temporal intelligence, prediction reliability assessment and risk-aware decision-making to anticipate thermal anomalies and support safe, energy-efficient cooling and workload optimisation.

**Approach:** Predict → Verify → Reason → Act  
**Implementation:** HaritAyush

## Person 2: Windows local agent

The agent implementation and Windows setup are in [`apps/local-agent`](apps/local-agent/README.md). It publishes CPU and memory usage every 3 seconds, reports CPU temperature only when a real Windows sensor is available, and handles the isolated demo workload, approved CPU caps, local kill switch, rollback and audit/outbox delivery.

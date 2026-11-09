# Ownership and contribution boundaries

HaritAyush is developed by three people. The repository is divided so that each
owner can work without restructuring the project or colliding with another
owner's source files.

## Ownership map

| Location | Owner | Responsibility |
| --- | --- | --- |
| `apps/frontend/**` | Person 1 — Frontend and Infrastructure | React application, Three.js 3D command centre, dashboard and visualisation, frontend API integration |
| `apps/local-agent/**` | Person 2 — Windows Local Agent | Windows 11 capability discovery, telemetry collection, agent architecture, secure backend communication, safe workload execution, checkpointing, compatible workload migration, local command validation |
| `apps/backend/**` | Person 3 — Backend and AI Intelligence | FastAPI application, database and repositories, backend APIs, shared data contracts, forecasting, verification, thermal risk, placement optimisation, sustainability calculations, device and workload coordination |
| `contracts/**` | Person 3 | Shared JSON Schema contracts |
| `infrastructure/**` | Person 1 | Container and deployment configuration |
| `docs/**` | Person 1 | Architecture, API and development documentation |
| `.github/**` | Person 1 | CI and repository workflows |
| Root configuration files (`README.md`, `.gitignore`, `docker-compose.yml`) | Person 1 | Repository foundation |

## Rules

1. **Work inside your own location.** Implementation changes belong to the owner
   of the directory. Reviewing or proposing changes elsewhere is expected;
   editing another owner's area needs their agreement first.
2. **One implementation per concern.** Do not create a second copy of a model,
   service, telemetry path or type definition in another application. Shared
   representations live in `contracts/` and are owned by Person 3.
3. **Contracts are agreed, not assumed.** The files in `contracts/` are
   placeholders. Person 3 designs them; Person 1 and Person 2 consume them.
   Changes that affect the agent or frontend payloads are coordinated before
   implementation.
4. **Dependencies stay isolated.** Frontend dependencies live only in
   `apps/frontend/package.json`. Python dependencies live only in each
   application's `pyproject.toml`. Do not add a root-level manifest unless the
   team agrees and documents why.
5. **Safety rules are not negotiable.** The constraints in
   `docs/architecture/safety-and-architecture-principles.md` apply to every
   owner's code, especially the agent's local safety validation and the
   backend's placement decisions.
6. **Do not claim unverified results.** Do not commit fabricated telemetry,
   invented forecast values or unreproduced accuracy numbers.

## Where a change crosses boundaries

| Change | Coordinate with |
| --- | --- |
| New or changed contract field | Person 3 (owner), then Person 1 and Person 2 |
| New backend endpoint or WebSocket message | Person 3, then Person 1 (consumes), Person 2 (if agent-facing) |
| New telemetry field collected by the agent | Person 2, then Person 3 (contract and storage), Person 1 (display) |
| New dependency or build step | The owning person, plus Person 1 if it affects CI |
| New top-level directory | Person 1, with a documented technical reason |

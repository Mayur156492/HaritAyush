"""Application entry point for the HaritAyush backend API."""

from fastapi import FastAPI

app = FastAPI(
    title="HaritAyush Backend",
    version="0.1.0",
    description=(
        "Distributed Thermal Intelligence and Resource Optimisation Platform. "
        "Scaffold build with telemetry ingestion, forecasting, risk, actions and audit."
    ),
)

# Include API routers
from app.api.routes.readings import router as readings_router
from app.api.routes.forecast import router as forecast_router
from app.api.routes.readings_recent import router as readings_recent_router
from app.api.routes.actions import router as actions_router
from app.api.routes.commands import router as commands_router
from app.api.routes.audit import router as audit_router

app.include_router(readings_router, prefix="/readings", tags=["telemetry"])
app.include_router(forecast_router, prefix="/forecast", tags=["forecast"])
app.include_router(readings_recent_router, prefix="/readings/recent", tags=["telemetry"])
app.include_router(actions_router, prefix="/actions", tags=["actions"])
app.include_router(commands_router, prefix="/commands", tags=["commands"])
app.include_router(audit_router, prefix="/audit", tags=["audit"])


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    """Report that the backend application is running.

    This endpoint deliberately performs no dependency checks: it reports
    process liveness only, not database, model or agent readiness.
    """
    return {"status": "ok", "service": "haritayush-backend"}
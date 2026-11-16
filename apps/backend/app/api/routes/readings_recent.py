"""GET /readings/recent — Return recent stored readings."""

from __future__ import annotations

from fastapi import APIRouter, Query, HTTPException

from ...schemas import ReadingRecent, RecentReadingsResponse
from ...models import Reading
from ...services.reading_service import get_recent_readings
from ...services import replay_state, replay_service


router = APIRouter(tags=["telemetry"])


@router.get(
    "",
    response_model=RecentReadingsResponse,
    summary="Get recent stored readings",
    description="Return recent stored readings for a device. Supports the "
    "`n` query parameter with a maximum of 1000 records.",
)
async def get_recent_readings_endpoint(
    n: int = Query(120, ge=1, le=1000, description="Number of recent readings to return (max 1000)"),
    site_id: str = Query("laptop-01", description="Site/device identifier"),
):
    """Get recent readings for a device."""
    if replay_state.is_replay_enabled():
        readings = replay_service.get_replay_history(site_id=site_id, n=n)
    else:
        readings = get_recent_readings(site_id=site_id, n=n)
    return RecentReadingsResponse(
        site_id=site_id,
        n=len(readings),
        readings=readings,
    )
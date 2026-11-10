"""POST /replay — Switch between live and replay data modes.

Replay mode streams a fixed saved readings file through the existing
reading/forecast pipeline instead of live telemetry. This provides the
backup demo path described in PRD Section D6 / Hour 11-12 task.

Safety rules:
- No arbitrary filesystem path may be supplied via the API.
- Replay mode blocks CPU-cap command delivery (enforced in /commands/pending).
- Replay mode does NOT persist readings to the database.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from ...services import replay_state, replay_service


router = APIRouter(tags=["replay"])


class ReplayRequest(BaseModel):
    enabled: bool


class ReplayResponse(BaseModel):
    data_mode: str  # "replay" | "live"


@router.post(
    "",
    response_model=ReplayResponse,
    summary="Enable or disable replay mode",
    description=(
        "Switch between live telemetry and saved-file replay. "
        "When enabled=true the backend streams readings from the fixed server-side "
        "replay file (data/sample/replay.jsonl). "
        "When enabled=false the backend returns to live telemetry. "
        "Replay mode is the backup demo path; it blocks CPU-cap command delivery."
    ),
)
def set_replay_mode(body: ReplayRequest) -> ReplayResponse:
    """Enable or disable replay mode."""
    if body.enabled:
        try:
            replay_service.load_replay_file()
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc
        replay_service.reset_replay_position()
        replay_state.enable_replay()
        return ReplayResponse(data_mode="replay")
    else:
        replay_state.disable_replay()
        return ReplayResponse(data_mode="live")


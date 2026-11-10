"""POST /actions/{id}/approve and POST /actions/{id}/dismiss endpoints.

Operator approval and dismissal of recommendations.  Per PRD section 5.D:
- Only an existing pending recommendation may be approved or dismissed.
- Preserve the operator's name and decision time.
- Record the decision in the audit trail.
- Prevent duplicate or contradictory decisions.
- Ensure that dismissal never results in command delivery.
- Ensure that approval is required before the agent receives the cpu_cap command.
"""

from __future__ import annotations

from fastapi import APIRouter, Path, HTTPException, status

from ...schemas import ApprovalPayload
from ...models import Recommendation, Decision, AuditRecord
from ...services.action_service import approve_recommendation, dismiss_recommendation


router = APIRouter(tags=["actions"])


@router.post(
    "/{rec_id}/approve",
    status_code=status.HTTP_200_OK,
    summary="Approve a recommendation",
    description="Operator approves a pending recommendation.  The decision is "
    "recorded in the audit trail.  Approval is required before the agent receives "
    "the cpu_cap command.",
)
async def approve_action(
    rec_id: str = Path(..., description="Recommendation identifier (numeric ID or action_id)"),
    payload: ApprovalPayload = ApprovalPayload(),
):
    """Approve a pending recommendation."""
    result = approve_recommendation(rec_id, payload.operator, payload.reason)
    if not result.get("approved"):
        raise HTTPException(
            status_code=result.get("status_code", status.HTTP_400_BAD_REQUEST),
            detail=result["error"],
        )

    return {
        "rec_id": result["rec_id"],
        "status": "approved",
        "operator": result["operator"],
        "decision_time": result["decision_time"],
        "command_delivered": result["command_delivered"],
    }


@router.post(
    "/{rec_id}/dismiss",
    status_code=status.HTTP_200_OK,
    summary="Dismiss a recommendation",
    description="Operator dismisses a pending recommendation.  Dismissal never "
    "results in command delivery.  The decision is recorded in the audit trail.",
)
async def dismiss_action(
    rec_id: str = Path(..., description="Recommendation identifier (numeric ID or action_id)"),
    payload: ApprovalPayload = ApprovalPayload(),
):
    """Dismiss a pending recommendation."""
    result = dismiss_recommendation(rec_id, payload.operator, payload.reason)
    if not result.get("dismissed"):
        raise HTTPException(
            status_code=result.get("status_code", status.HTTP_400_BAD_REQUEST),
            detail=result["error"],
        )

    return {
        "rec_id": result["rec_id"],
        "status": "dismissed",
        "operator": result["operator"],
        "decision_time": result["decision_time"],
        "command_delivered": False,
    }
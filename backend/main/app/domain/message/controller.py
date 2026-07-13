"""Outbound-message admin controller.

URL shape: /messages — the bookkeeping rows themselves have no public listing
(they carry recipient PII); only the retry sweep trigger is exposed, RBAC-gated.
"""
from fastapi import APIRouter, Depends
from kink import di

from main.app.domain.user.auth.utils.permissions import Permission, require_permission
from main.appodus_utils.db.models import SuccessResponse
from main.appodus_utils.integrations.messaging.service import MessagingService

message_router = APIRouter(prefix="/messages", tags=["Messages"])


@message_router.post("/sweeps/retries", response_model=SuccessResponse[dict])
async def sweep_message_retries(
    _admin_id: str = Depends(require_permission(Permission.CONFIGURE_SYSTEM)),
):
    """Re-dispatch RETRYING outbound messages whose next_retry_at has passed
    (backoff ladder + expires_at horizon). Runs on a schedule in non-test envs;
    this endpoint triggers it on demand (idempotent)."""
    stats = await di[MessagingService].process_retries()
    return SuccessResponse[dict](data=stats)

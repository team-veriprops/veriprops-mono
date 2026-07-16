"""Dev/QA endpoints (non-production only). URL shape: /dev/...

Production-gated twice (CLAUDE.md automation determinism): this router is only mounted in
non-prod (see app/domain/__init__.py), and every handler calls `_require_non_prod()` which
returns 404 in production.
"""
from __future__ import annotations

from fastapi import APIRouter
from kink import di

from main.app.config.settings import settings
from main.app.domain.dev.service import DevSeedService
from main.appodus_utils.config.settings import Environment
from main.appodus_utils.db.models import SuccessResponse
from main.appodus_utils.exception.exceptions import ResourceNotFoundException

dev_router = APIRouter(prefix="/dev", tags=["Dev"])
service: DevSeedService = di[DevSeedService]


def _require_non_prod() -> None:
    """404 in production — the second guard behind the non-prod router mount."""
    if settings.ENVIRONMENT == Environment.PRODUCTION:
        raise ResourceNotFoundException(resource="Not found")


@dev_router.post("/reset", response_model=SuccessResponse[dict])
async def reset():
    _require_non_prod()
    return SuccessResponse[dict](data=await service.reset())


@dev_router.post("/seed", response_model=SuccessResponse[dict])
async def seed():
    _require_non_prod()
    return SuccessResponse[dict](data=await service.seed())


@dev_router.get("/messages/latest", response_model=SuccessResponse[dict])
async def latest_message(recipient: str):
    """Bookkeeping snapshot of the newest outbound message to *recipient* — lets the
    drive-through's messaging_retry stage assert stored/retrying/failed/sent state."""
    _require_non_prod()
    return SuccessResponse[dict](data=await service.latest_message(recipient))


@dev_router.post("/messages/rewind", response_model=SuccessResponse[dict])
async def rewind_message(recipient: str, rewind_expiry: bool = False):
    """Pull the newest matching message's next_retry_at (and optionally expires_at) into
    the past so the retry sweep fires immediately — determinism helper for e2e runs
    against the default backoff ladder."""
    _require_non_prod()
    return SuccessResponse[dict](data=await service.rewind_message(recipient, rewind_expiry))

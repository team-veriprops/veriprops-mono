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

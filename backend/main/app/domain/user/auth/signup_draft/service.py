from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger

import json
from datetime import timedelta
from typing import Any, Dict, Optional

from kink import di, inject

from main.app.domain.user.auth.signup_draft.models import (
    CreateSignupDraftDto,
    SignupDraft,
    SignupDraftDto,
    UpdateSignupDraftDto,
)
from main.app.domain.user.auth.signup_draft.repo import SignupDraftRepo
from main.appodus_utils import Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional

logger: Logger = di["logger"]

DRAFT_TTL = timedelta(days=7)


@inject
@decorate_all_methods(transactional(), exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class SignupDraftService:
    def __init__(self, repo: SignupDraftRepo):
        self._repo = repo

    async def upsert(self, *, email: str, step: int, payload: Dict[str, Any]) -> SignupDraftDto:
        normalised = email.lower()
        encoded = json.dumps(payload)
        expires_at = Utils.datetime_now_plus(seconds=int(DRAFT_TTL.total_seconds()))

        existing = await self._repo.get_active_by_email(normalised)
        if existing:
            await self._repo.update(
                str(existing.id),
                UpdateSignupDraftDto(step=step, payload=encoded, expires_at=expires_at),
            )
            row = await self._repo.get_active_by_email(normalised)
        else:
            await self._repo.create(CreateSignupDraftDto(
                email=normalised, step=step, payload=encoded, expires_at=expires_at,
            ))
            row = await self._repo.get_active_by_email(normalised)

        return self._to_dto(row)

    async def get(self, email: str) -> Optional[SignupDraftDto]:
        row = await self._repo.get_active_by_email(email.lower())
        return self._to_dto(row) if row else None

    async def discard(self, email: str) -> None:
        existing = await self._repo.get_active_by_email(email.lower())
        if existing:
            # Soft-delete via GenericRepo; deleted rows are excluded by
            # `get_active_by_email` so a fresh signup will create a new draft.
            await self._repo.soft_delete(str(existing.id))

    @staticmethod
    def _to_dto(row: Optional[SignupDraft]) -> Optional[SignupDraftDto]:
        if not row:
            return None
        try:
            payload = json.loads(row.payload) if row.payload else {}
        except json.JSONDecodeError:
            logger.warning("Discarding malformed signup draft payload for {}", row.email)
            payload = {}
        return SignupDraftDto(
            email=row.email,
            step=row.step,
            payload=payload,
            updated_at=row.date_updated or row.date_created,
        )

"""Share link service — S43."""
from __future__ import annotations

import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional

from kink import di, inject

from main.app.domain.verification.share.models import (
    CreateShareDto,
    CreateShareLinkDto,
    CreateShareRecipientDto,
    ShareLinkDto,
    ShareMode,
)
from main.app.domain.verification.share.repo import ShareLinkRepo, ShareRecipientRepo
from main.appodus_utils import Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import (
    ForbiddenException,
    ResourceNotFoundException,
    ValidationException,
)


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class ShareService:
    def __init__(self, repo: ShareLinkRepo, recipient_repo: ShareRecipientRepo):
        self._repo = repo
        self._recipient_repo = recipient_repo

    async def create(
        self, verification_id: str, customer_id: str, dto: CreateShareDto,
    ) -> ShareLinkDto:
        if dto.mode == ShareMode.NAMED_RECIPIENT and not dto.recipient_email:
            raise ValidationException(message="recipient_email required for NAMED_RECIPIENT mode")

        expires_at = (
            Utils.datetime_now() + timedelta(days=dto.expiry_days)
        ) if dto.expiry_days else None

        token = secrets.token_urlsafe(32)
        row = await self._repo.create(CreateShareLinkDto(
            verification_id=verification_id,
            mode=dto.mode,
            token=token,
            expires_at=str(expires_at) if expires_at else None,
            created_by=customer_id,
        ))

        if dto.mode == ShareMode.NAMED_RECIPIENT and dto.recipient_email:
            await self._recipient_repo.create(CreateShareRecipientDto(
                share_link_id=str(row.id),
                email=dto.recipient_email,
            ))

        return self._to_dto(row)

    async def revoke(self, share_link_id: str, customer_id: str) -> None:
        row = await self._repo.get_model(share_link_id)
        if row is None:
            raise ResourceNotFoundException(resource="ShareLink")
        if str(row.created_by) != customer_id:
            raise ForbiddenException(message="Not your share link")
        from main.app.domain.verification.share.models import UpdateShareLinkDto
        await self._repo.update(share_link_id, UpdateShareLinkDto(revoked_at=str(Utils.datetime_now())))

    async def get_by_token(self, token: str):
        row = await self._repo.get_by_token(token)
        if row is None:
            raise ResourceNotFoundException(resource="ShareLink")
        if row.revoked_at is not None:
            raise ForbiddenException(message="Share link has been revoked")
        if row.expires_at and datetime.fromisoformat(str(row.expires_at)) < datetime.now(timezone.utc):
            raise ValidationException(message="Share link has expired")
        return self._to_dto(row)

    async def acknowledge(self, token: str) -> None:
        row = await self._repo.get_by_token(token)
        if row is None:
            raise ResourceNotFoundException(resource="ShareLink")
        # find recipient and record acknowledgement
        from main.appodus_utils.db.session import get_db_session_from_context
        from sqlalchemy import select
        from main.app.domain.verification.share.models import ShareRecipient, UpdateShareRecipientDto
        session = get_db_session_from_context()
        result = await session.execute(
            select(ShareRecipient).where(
                ShareRecipient.share_link_id == str(row.id),
                ShareRecipient.deleted == False,
            )
        )
        recipient = result.scalars().first()
        if recipient and recipient.acknowledged_at is None:
            await self._recipient_repo.update(
                str(recipient.id),
                UpdateShareRecipientDto(acknowledged_at=str(Utils.datetime_now())),
            )

    def _to_dto(self, row) -> ShareLinkDto:
        return ShareLinkDto(
            id=str(row.id),
            verification_id=str(row.verification_id),
            mode=ShareMode(row.mode),
            token=row.token,
            expires_at=str(row.expires_at) if row.expires_at else None,
            revoked_at=str(row.revoked_at) if row.revoked_at else None,
            created_by=str(row.created_by),
            date_created=str(row.date_created),
        )

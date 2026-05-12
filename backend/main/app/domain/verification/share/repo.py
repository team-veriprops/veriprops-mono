"""Share link repos — S43."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from kink import inject

from main.app.domain.verification.share.models import (
    ShareLink,
    ShareRecipient,
    CreateShareLinkDto,
    UpdateShareLinkDto,
    QueryShareLinkDto,
    SearchShareLinkDto,
    CreateShareRecipientDto,
    UpdateShareRecipientDto,
    QueryShareRecipientDto,
)
from main.appodus_utils.db.repo import GenericRepo
from main.appodus_utils.db.session import get_db_session_from_context


@inject
class ShareLinkRepo(GenericRepo[
    ShareLink,
    CreateShareLinkDto,
    UpdateShareLinkDto,
    QueryShareLinkDto,
    SearchShareLinkDto,
]):
    model = ShareLink

    async def get_by_token(self, token: str) -> Optional[ShareLink]:
        session = get_db_session_from_context()
        result = await session.execute(
            select(ShareLink).where(ShareLink.token == token, ShareLink.deleted == False)
        )
        return result.scalars().first()


@inject
class ShareRecipientRepo(GenericRepo[
    ShareRecipient,
    CreateShareRecipientDto,
    UpdateShareRecipientDto,
    QueryShareRecipientDto,
    SearchShareLinkDto,
]):
    model = ShareRecipient

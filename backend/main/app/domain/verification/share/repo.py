"""Share link repos — S43."""
from __future__ import annotations

from typing import Optional, Type

from sqlalchemy import select
from kink import inject
from sqlalchemy.ext.asyncio import AsyncSession

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
    def __init__(
        self,
        db: AsyncSession,
        model: Type[ShareLink] = ShareLink,
        query_dto: Type[QueryShareLinkDto] = QueryShareLinkDto,
    ):
        super().__init__(db, model, query_dto)

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
    def __init__(
        self,
        db: AsyncSession,
        model: Type[ShareRecipient] = ShareRecipient,
        query_dto: Type[QueryShareRecipientDto] = QueryShareRecipientDto,
    ):
        super().__init__(db, model, query_dto)

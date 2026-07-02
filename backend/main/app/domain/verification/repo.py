from typing import Optional, Type

from kink import inject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.verification.models import (
    CreateVerificationDto,
    QueryVerificationDto,
    SearchVerificationDto,
    UpdateVerificationDto,
    Verification,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class VerificationRepo(
    GenericRepo[
        Verification,
        CreateVerificationDto,
        UpdateVerificationDto,
        QueryVerificationDto,
        SearchVerificationDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[Verification] = Verification,
        query_dto: Type[QueryVerificationDto] = QueryVerificationDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def get_by_vid(self, vid: str) -> Optional[Verification]:
        stmt = select(Verification).where(
            Verification.deleted.is_(False),
            Verification.vid == vid,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

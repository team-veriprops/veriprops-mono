"""Report share data access."""
from __future__ import annotations

from typing import List, Optional, Type

from kink import inject
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.verification.share.models import (
    CreateVerificationShareDto,
    QueryVerificationShareDto,
    SearchVerificationShareDto,
    UpdateVerificationShareDto,
    VerificationShare,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class VerificationShareRepo(
    GenericRepo[
        VerificationShare,
        CreateVerificationShareDto,
        UpdateVerificationShareDto,
        QueryVerificationShareDto,
        SearchVerificationShareDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[VerificationShare] = VerificationShare,
        query_dto: Type[QueryVerificationShareDto] = QueryVerificationShareDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def get_by_token(self, token: str) -> Optional[VerificationShare]:
        stmt = select(VerificationShare).where(
            VerificationShare.deleted.is_(False),
            VerificationShare.token == token,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_for_verification(self, verification_id: str) -> List[VerificationShare]:
        stmt = (
            select(VerificationShare)
            .where(
                VerificationShare.deleted.is_(False),
                VerificationShare.verification_id == verification_id,
            )
            .order_by(desc(VerificationShare.date_created))
        )
        return list((await self._session.execute(stmt)).scalars().all())

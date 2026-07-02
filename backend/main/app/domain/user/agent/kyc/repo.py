from typing import Optional, Type

from kink import inject
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.user.agent.kyc.models import (
    CreateKycRecordDto,
    KycRecord,
    QueryKycRecordDto,
    SearchKycRecordDto,
    UpdateKycRecordDto,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class KycRecordRepo(
    GenericRepo[
        KycRecord,
        CreateKycRecordDto,
        UpdateKycRecordDto,
        QueryKycRecordDto,
        SearchKycRecordDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[KycRecord] = KycRecord,
        query_dto: Type[QueryKycRecordDto] = QueryKycRecordDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def get_latest_for_user(self, user_id: str) -> Optional[KycRecord]:
        stmt = (
            select(KycRecord)
            .where(
                KycRecord.deleted.is_(False),
                KycRecord.user_id == user_id,
            )
            .order_by(desc(KycRecord.date_created))
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

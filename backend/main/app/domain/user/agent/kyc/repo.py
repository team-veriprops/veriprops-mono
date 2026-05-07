from __future__ import annotations

from typing import Optional, Type

from kink import inject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.user.agent.kyc.models import (
    CreateKycRecordDto,
    KycRecord,
    KycStatus,
    KycType,
    QueryKycRecordDto,
    SearchKycRecordDto,
    UpdateKycRecordDto,
)
from main.appodus_utils.db.models import Page
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

    async def get_by_provider_ref(self, provider_ref: str) -> Optional[KycRecord]:
        stmt = (
            select(KycRecord)
            .where(
                KycRecord.deleted.is_(False),
                KycRecord.provider_ref == provider_ref,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_latest_for_application(
        self, application_id: str, kyc_type: KycType
    ) -> Optional[KycRecord]:
        stmt = (
            select(KycRecord)
            .where(
                KycRecord.deleted.is_(False),
                KycRecord.application_id == application_id,
                KycRecord.kyc_type == kyc_type.value,
            )
            .order_by(KycRecord.date_created.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_under_review(
        self, page: int = 1, page_size: int = 25
    ) -> Page[KycRecord]:
        search = SearchKycRecordDto(
            page=page,
            page_size=page_size,
            status=KycStatus.UNDER_REVIEW.value,
        )
        return await self.get_page(search)

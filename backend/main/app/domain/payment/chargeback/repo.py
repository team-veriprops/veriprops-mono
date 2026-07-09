"""Chargeback data access."""
from __future__ import annotations

from typing import List, Optional, Type

from kink import inject
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.payment.chargeback.models import (
    Chargeback,
    CreateChargebackDto,
    QueryChargebackDto,
    SearchChargebackDto,
    UpdateChargebackDto,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class ChargebackRepo(
    GenericRepo[
        Chargeback,
        CreateChargebackDto,
        UpdateChargebackDto,
        QueryChargebackDto,
        SearchChargebackDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[Chargeback] = Chargeback,
        query_dto: Type[QueryChargebackDto] = QueryChargebackDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def get_by_event_id(self, gateway_event_id: str) -> Optional[Chargeback]:
        stmt = select(Chargeback).where(
            Chargeback.deleted.is_(False),
            Chargeback.gateway_event_id == gateway_event_id,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_for_verification(self, verification_id: str) -> List[Chargeback]:
        stmt = select(Chargeback).where(
            Chargeback.deleted.is_(False),
            Chargeback.verification_id == verification_id,
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def count_by_status(self, statuses: List[str]) -> int:
        """Chargebacks currently in any of the given statuses (admin dashboard §6a)."""
        stmt = select(func.count()).select_from(Chargeback).where(
            Chargeback.deleted.is_(False),
            Chargeback.status.in_(statuses),
        )
        return int(await self._session.scalar(stmt) or 0)

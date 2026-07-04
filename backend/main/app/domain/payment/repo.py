from typing import List, Optional, Type

from kink import inject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.payment.models import (
    CreatePaymentDto,
    Payment,
    QueryPaymentDto,
    SearchPaymentDto,
    UpdatePaymentDto,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class PaymentRepo(
    GenericRepo[Payment, CreatePaymentDto, UpdatePaymentDto, QueryPaymentDto, SearchPaymentDto]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[Payment] = Payment,
        query_dto: Type[QueryPaymentDto] = QueryPaymentDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def get_by_tx_ref(self, tx_ref: str) -> Optional[Payment]:
        stmt = select(Payment).where(
            Payment.deleted.is_(False),
            Payment.tx_ref == tx_ref,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_verification(self, verification_id: str) -> List[Payment]:
        stmt = select(Payment).where(
            Payment.deleted.is_(False),
            Payment.verification_id == verification_id,
        )
        return list((await self._session.execute(stmt)).scalars().all())

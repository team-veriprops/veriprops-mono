from typing import Optional, Type

from kink import inject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.payment.models import (
    CreatePaymentAttemptDto,
    CreatePaymentDto,
    Payment,
    PaymentAttempt,
    QueryPaymentAttemptDto,
    QueryPaymentDto,
    SearchPaymentAttemptDto,
    SearchPaymentDto,
    UpdatePaymentAttemptDto,
    UpdatePaymentDto,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class PaymentRepo(
    GenericRepo[
        Payment, CreatePaymentDto, UpdatePaymentDto, QueryPaymentDto, SearchPaymentDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[Payment] = Payment,
        query_dto: Type[QueryPaymentDto] = QueryPaymentDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def get_by_provider_ref(self, provider_ref: str) -> Optional[Payment]:
        stmt = (
            select(Payment)
            .where(
                Payment.deleted.is_(False),
                Payment.provider_ref == provider_ref,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()


@inject
class PaymentAttemptRepo(
    GenericRepo[
        PaymentAttempt,
        CreatePaymentAttemptDto,
        UpdatePaymentAttemptDto,
        QueryPaymentAttemptDto,
        SearchPaymentAttemptDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[PaymentAttempt] = PaymentAttempt,
        query_dto: Type[QueryPaymentAttemptDto] = QueryPaymentAttemptDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

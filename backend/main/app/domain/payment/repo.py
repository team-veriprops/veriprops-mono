from typing import List, Optional, Tuple, Type

from kink import inject
from sqlalchemy import func, select
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

    async def admin_list(
        self,
        status: Optional[str],
        method: Optional[str],
        page: int,
        page_size: int,
    ):
        from sqlalchemy import func, select
        from main.appodus_utils.db.session import get_db_session_from_context
        session = self._session
        filters = [Payment.deleted.is_(False)]
        if status:
            filters.append(Payment.status == status)
        if method:
            filters.append(Payment.method == method)
        total = await session.scalar(select(func.count(Payment.id)).where(*filters)) or 0
        offset = page * page_size
        result = await session.execute(
            select(Payment).where(*filters).order_by(Payment.date_created.desc()).offset(offset).limit(page_size)
        )
        return list(result.scalars().all()), int(total)

    async def list_for_customer(
        self, customer_id: str, page: int = 0, page_size: int = 20,
    ) -> Tuple[List[Tuple[Payment, str]], int]:
        """Return (Payment, vid) pairs for all non-deleted payments belonging to a customer."""
        from main.app.domain.verification.models import Verification

        session = self._session
        join_cond = Payment.verification_id == Verification.id
        filters = [
            Payment.deleted.is_(False),
            Verification.deleted.is_(False),
            Verification.customer_id == customer_id,
        ]

        total = await session.scalar(
            select(func.count(Payment.id)).join(Verification, join_cond).where(*filters)
        ) or 0

        result = await session.execute(
            select(Payment, Verification.vid)
            .join(Verification, join_cond)
            .where(*filters)
            .order_by(Payment.date_created.desc())
            .offset(page * page_size)
            .limit(page_size)
        )
        rows = [(row.Payment, row.vid) for row in result]
        return rows, int(total)

    async def count_succeeded_for_user(self, user_id: str) -> int:
        """Count SUCCEEDED payments made by the given customer.

        Used to determine whether this is the customer's first payment and
        whether a first-time discount should be applied.
        """
        from main.app.domain.verification.models import Verification
        from main.app.domain.payment.models import PaymentStatus

        # Join Payment → Verification to filter by customer_id
        stmt = (
            select(func.count(Payment.id))
            .join(Verification, Payment.verification_id == Verification.id, isouter=False)
            .where(
                Payment.deleted.is_(False),
                Payment.status == PaymentStatus.SUCCEEDED.value,
                Verification.customer_id == user_id,
                Verification.deleted.is_(False),
            )
        )
        return await self._session.scalar(stmt) or 0


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

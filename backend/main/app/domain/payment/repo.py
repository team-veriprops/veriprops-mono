from typing import List, Optional, Type

from kink import inject
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.payment.models import (
    CreatePaymentDto,
    Payment,
    PaymentStatus,
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

    async def sum_succeeded_amount(self) -> int:
        """Total collected revenue — sum of SUCCEEDED payment NGN amounts (Mission Control §18.1)."""
        stmt = select(func.coalesce(func.sum(Payment.amount_minor), 0)).where(
            Payment.deleted.is_(False),
            Payment.status == PaymentStatus.SUCCEEDED.value,
        )
        return int(await self._session.scalar(stmt) or 0)

    async def count_by_status(self) -> dict:
        """status → count over all payments (Finance panel §18.1)."""
        stmt = select(Payment.status, func.count()).where(
            Payment.deleted.is_(False)
        ).group_by(Payment.status)
        return {s: int(c) for s, c in (await self._session.execute(stmt)).all()}

    async def revenue_by_verification(self) -> dict[str, int]:
        """verification_id → collected revenue (SUCCEEDED sum), for analytics (§18.1)."""
        stmt = select(Payment.verification_id, func.sum(Payment.amount_minor)).where(
            Payment.deleted.is_(False),
            Payment.status == PaymentStatus.SUCCEEDED.value,
        ).group_by(Payment.verification_id)
        return {vid: int(total or 0) for vid, total in (await self._session.execute(stmt)).all()}

    async def count_for_customer(self, customer_id: str) -> int:
        """How many payments a customer has made — the admin user-detail panel (§4.2)."""
        stmt = select(func.count()).select_from(Payment).where(
            Payment.deleted.is_(False),
            Payment.customer_id == customer_id,
        )
        return int(await self._session.scalar(stmt) or 0)

    async def list_card_fingerprints_for_customer(self, customer_id: str) -> set[str]:
        """Distinct non-null card fingerprints a customer has ever paid with — the referral
        anti-farming check (§17.1, D34) rejects a referrer/invitee sharing an instrument."""
        stmt = select(Payment.card_fingerprint).where(
            Payment.deleted.is_(False),
            Payment.customer_id == customer_id,
            Payment.card_fingerprint.is_not(None),
        )
        return {row for row in (await self._session.execute(stmt)).scalars().all() if row}

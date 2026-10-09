from typing import List, Optional, Tuple, Type

from kink import inject
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.payment.models import (
    CreatePaymentDto,
    Payment,
    PaymentStatus,
    QueryPaymentDto,
    SearchPaymentDto,
    UpdatePaymentDto,
)
from main.app.domain.verification.models import Verification
from main.appodus_utils.db.db_utils import hex_ref
from main.appodus_utils.db.repo import GenericRepo
from main.appodus_utils.db.search import contains_text


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

    async def get_by_gateway_reference(self, provider: str, gateway_reference: str) -> Optional[Payment]:
        """The payment a gateway identifies by its own reference (a chargeback that cites no tx_ref)."""
        stmt = select(Payment).where(
            Payment.deleted.is_(False),
            Payment.provider == provider,
            Payment.gateway_reference == gateway_reference,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def page_refunds_to_retry(self, page: int, page_size: int) -> Tuple[List[Payment], int]:
        """Charges still owing an approved refund their gateway refused, oldest first: what
        Finance retries. A charge under a chargeback is the issuer's to settle, never ours."""
        stmt = select(Payment).where(
            Payment.deleted.is_(False),
            Payment.status == PaymentStatus.SUCCEEDED.value,
            Payment.chargeback_status.is_(None),
            Payment.refund_due_minor > 0,
        )
        total = await self._session.scalar(select(func.count()).select_from(stmt.subquery()))
        rows = await self._session.execute(
            stmt.order_by(Payment.date_created.asc()).offset(page * page_size).limit(page_size)
        )
        return list(rows.scalars().all()), int(total or 0)

    async def page_for_admin(
        self, page: int, page_size: int, query: Optional[str] = None, status: Optional[PaymentStatus] = None,
    ) -> Tuple[List[Tuple[Payment, str]], int]:
        """Every live payment with its case's VID, newest first (finance's payments list).
        *query* matches the charge reference or the VID, as typed: its wildcards are escaped."""
        criteria = [Payment.deleted.is_(False)]
        if status is not None:
            criteria.append(Payment.status == status.value)
        search = contains_text(query, Payment.tx_ref, Verification.vid)
        if search is not None:
            criteria.append(search)
        joined = (
            select(Payment, Verification.vid)
            .join(Verification, hex_ref(Verification.id) == Payment.verification_id)
            .where(*criteria)
        )
        total = await self._session.scalar(select(func.count()).select_from(joined.subquery()))
        rows = await self._session.execute(
            joined.order_by(Payment.date_created.desc()).offset(page * page_size).limit(page_size)
        )
        return [tuple(row) for row in rows.all()], int(total or 0)

    async def list_for_verification(self, verification_id: str) -> List[Payment]:
        stmt = select(Payment).where(
            Payment.deleted.is_(False),
            Payment.verification_id == verification_id,
        ).order_by(Payment.date_created.asc())
        return list((await self._session.execute(stmt)).scalars().all())

    async def sum_collected_revenue(self) -> int:
        """What Veriprops kept, in NGN minor units (Mission Control §18.1): settled charges in
        full, and of a refunded charge what the refund did not return (the surcharge of a
        withdrawal, say) — nothing after a full refund."""
        kept = case(
            (Payment.status == PaymentStatus.SUCCEEDED.value, Payment.amount_minor),
            (Payment.status == PaymentStatus.REFUNDED.value,
             Payment.amount_minor - func.coalesce(Payment.refunded_amount_minor, Payment.amount_minor)),
            else_=0,
        )
        stmt = select(func.coalesce(func.sum(kept), 0)).where(Payment.deleted.is_(False))
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

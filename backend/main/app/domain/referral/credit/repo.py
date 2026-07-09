"""Referral-credit ledger data access."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Tuple, Type

from kink import inject
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.referral.credit.models import (
    CreateReferralCreditDto,
    QueryReferralCreditDto,
    ReferralCredit,
    ReferralCreditStatus,
    SearchReferralCreditDto,
    UpdateReferralCreditDto,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class ReferralCreditRepo(
    GenericRepo[
        ReferralCredit,
        CreateReferralCreditDto,
        UpdateReferralCreditDto,
        QueryReferralCreditDto,
        SearchReferralCreditDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[ReferralCredit] = ReferralCredit,
        query_dto: Type[QueryReferralCreditDto] = QueryReferralCreditDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def get_for_invitee(self, invitee_user_id: str) -> Optional[ReferralCredit]:
        """A single credit is earned per invitee (their first payment) — used as the
        idempotency guard so a re-run never mints a second credit for the same invitee."""
        stmt = select(ReferralCredit).where(
            ReferralCredit.deleted.is_(False),
            ReferralCredit.invitee_user_id == invitee_user_id,
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_for_referrer(self, referrer_user_id: str) -> List[ReferralCredit]:
        stmt = select(ReferralCredit).where(
            ReferralCredit.deleted.is_(False),
            ReferralCredit.referrer_user_id == referrer_user_id,
        ).order_by(ReferralCredit.date_created.desc())
        return list((await self._session.execute(stmt)).scalars().all())

    async def list_pending_due(self, now: datetime) -> List[ReferralCredit]:
        """PENDING credits whose chargeback window has passed — ready to clear (§17.1)."""
        stmt = select(ReferralCredit).where(
            ReferralCredit.deleted.is_(False),
            ReferralCredit.status == ReferralCreditStatus.PENDING.value,
            ReferralCredit.clearing_until.is_not(None),
            ReferralCredit.clearing_until <= now,
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def page_for_referrer(
        self, referrer_user_id: str, page: int, page_size: int
    ) -> Tuple[List[ReferralCredit], int]:
        base = select(ReferralCredit).where(
            ReferralCredit.deleted.is_(False),
            ReferralCredit.referrer_user_id == referrer_user_id,
        )
        total = (await self._session.execute(
            select(func.count()).select_from(base.subquery())
        )).scalar_one()
        stmt = base.order_by(ReferralCredit.date_created.desc()).offset(page * page_size).limit(page_size)
        rows = list((await self._session.execute(stmt)).scalars().all())
        return rows, total

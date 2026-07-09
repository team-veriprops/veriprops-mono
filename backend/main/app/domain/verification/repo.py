from datetime import date, datetime
from typing import List, Optional, Type

from kink import inject
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.core.state.status import VerificationStatus
from main.app.domain.verification.models import (
    CreateVerificationDto,
    QueryVerificationDto,
    SearchVerificationDto,
    UpdateVerificationDto,
    Verification,
)
from main.appodus_utils.db.repo import GenericRepo

# Pre-payment statuses a customer can still return to and complete (§17.1 abandonment).
_UNPAID_STATUSES = (
    VerificationStatus.DRAFT.value,
    VerificationStatus.SUBMITTED.value,
    VerificationStatus.PAYMENT_PENDING.value,
)


@inject
class VerificationRepo(
    GenericRepo[
        Verification,
        CreateVerificationDto,
        UpdateVerificationDto,
        QueryVerificationDto,
        SearchVerificationDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[Verification] = Verification,
        query_dto: Type[QueryVerificationDto] = QueryVerificationDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def get_by_vid(self, vid: str) -> Optional[Verification]:
        stmt = select(Verification).where(
            Verification.deleted.is_(False),
            Verification.vid == vid,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def page_for_customer(
        self, customer_id: str, offset: int = 0, limit: int = 10
    ) -> tuple[List[Verification], int]:
        """The customer's own verifications, newest first (My Verifications list §9)."""
        base = select(Verification).where(
            Verification.deleted.is_(False),
            Verification.customer_id == customer_id,
        )
        total = await self._session.scalar(select(func.count()).select_from(base.subquery()))
        rows = (
            await self._session.execute(
                base.order_by(Verification.date_created.desc()).offset(offset).limit(limit)
            )
        ).scalars().all()
        return list(rows), int(total or 0)

    async def has_paid_verification(self, customer_id: str, exclude_id: Optional[str] = None) -> bool:
        """True if the customer has ever paid for a verification (§17.1 first-time eligibility)."""
        conditions = [
            Verification.deleted.is_(False),
            Verification.customer_id == customer_id,
            Verification.paid_at.is_not(None),
        ]
        if exclude_id:
            conditions.append(Verification.id != exclude_id)
        stmt = select(func.count()).select_from(Verification).where(*conditions)
        return int(await self._session.scalar(stmt) or 0) > 0

    async def latest_unpaid_for_customer(self, customer_id: str) -> Optional[Verification]:
        """The customer's most recent still-completable verification, for the recovery
        banner (§17.1). A DRAFT with no progress (step 0) is ignored."""
        stmt = select(Verification).where(
            Verification.deleted.is_(False),
            Verification.customer_id == customer_id,
            Verification.paid_at.is_(None),
            Verification.status.in_(_UNPAID_STATUSES),
            or_(
                Verification.status != VerificationStatus.DRAFT.value,
                Verification.draft_step >= 1,
            ),
        ).order_by(Verification.date_updated.desc()).limit(1)
        return (await self._session.execute(stmt)).scalars().first()

    async def list_abandoned_drafts(self, cutoff: datetime) -> List[Verification]:
        """Unpaid, un-reminded verifications last touched before ``cutoff`` (§17.1 recovery
        sweep). One reminder ever — ``recovery_reminded_at`` gates re-sends."""
        stmt = select(Verification).where(
            Verification.deleted.is_(False),
            Verification.paid_at.is_(None),
            Verification.recovery_reminded_at.is_(None),
            Verification.status.in_(_UNPAID_STATUSES),
            Verification.date_updated < cutoff,
            or_(
                Verification.status != VerificationStatus.DRAFT.value,
                Verification.draft_step >= 1,
            ),
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def count_by_status_for_customer(self, customer_id: str) -> dict[str, int]:
        """status → count over a customer's own verifications (portal dashboard §9)."""
        stmt = (
            select(Verification.status, func.count())
            .where(
                Verification.deleted.is_(False),
                Verification.customer_id == customer_id,
            )
            .group_by(Verification.status)
        )
        rows = (await self._session.execute(stmt)).all()
        return {status: int(count) for status, count in rows}

    async def count_by_status(self) -> dict[str, int]:
        """status → count over every verification (admin dashboard §6)."""
        stmt = (
            select(Verification.status, func.count())
            .where(Verification.deleted.is_(False))
            .group_by(Verification.status)
        )
        rows = (await self._session.execute(stmt)).all()
        return {status: int(count) for status, count in rows}

    async def count_overdue(self, active_statuses: List[str], today: date) -> int:
        """Active verifications whose SLA due date has passed (admin dashboard §6.4)."""
        stmt = select(func.count()).select_from(Verification).where(
            Verification.deleted.is_(False),
            Verification.status.in_(active_statuses),
            Verification.sla_due_date.is_not(None),
            Verification.sla_due_date < today,
        )
        return int(await self._session.scalar(stmt) or 0)

    async def count_due_within(self, active_statuses: List[str], today: date, horizon: date) -> int:
        """Active verifications due between today and ``horizon`` (inclusive) but not yet
        overdue — the SLA-at-risk count for Mission Control (§18.1)."""
        stmt = select(func.count()).select_from(Verification).where(
            Verification.deleted.is_(False),
            Verification.status.in_(active_statuses),
            Verification.sla_due_date.is_not(None),
            Verification.sla_due_date >= today,
            Verification.sla_due_date <= horizon,
        )
        return int(await self._session.scalar(stmt) or 0)

    async def list_active_overdue(self, active_statuses: List[str], today: date) -> List[Verification]:
        """Active verifications past their SLA due date — the SLA-breach sweep source (§12.2)."""
        stmt = select(Verification).where(
            Verification.deleted.is_(False),
            Verification.status.in_(active_statuses),
            Verification.sla_due_date.is_not(None),
            Verification.sla_due_date < today,
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def analytics_snapshot(self) -> List[dict]:
        """Lightweight per-verification rows for analytics aggregation (§18.1): tier, status,
        paid_at, last-update (completion proxy for COMPLETED), and the property's state.
        Aggregated in the service — fine at MVP volume (cache/materialise if it grows)."""
        from main.app.domain.property.models import Property
        # verifications.property_id is String(36) while properties.id is a native UUID —
        # cast the UUID to text so asyncpg can compare them (the two-string-forms gotcha).
        stmt = select(
            Verification.id, Verification.tier, Verification.status,
            Verification.paid_at, Verification.date_updated, Property.state,
        ).select_from(Verification).join(
            Property, cast(Property.id, String) == Verification.property_id, isouter=True
        ).where(Verification.deleted.is_(False))
        rows = (await self._session.execute(stmt)).all()
        return [
            {"id": r[0], "tier": r[1], "status": r[2], "paid_at": r[3], "updated": r[4], "state": r[5]}
            for r in rows
        ]

    async def page_admin(
        self,
        *,
        status: Optional[str] = None,
        tier: Optional[str] = None,
        state_region: Optional[str] = None,
        query: Optional[str] = None,
        due_before: Optional[date] = None,
        offset: int = 0,
        limit: int = 10,
    ) -> tuple[List[Verification], int]:
        """Admin control-panel list (§6.1). SLA-health (on-track/at-risk/overdue) is
        computed in the service from ``sla_due_date``; the DB filters the coarse facets.
        ``query`` matches the customer-facing VID."""
        conditions = [Verification.deleted.is_(False)]
        if status:
            conditions.append(Verification.status == status)
        if tier:
            conditions.append(Verification.tier == tier)
        if query and query.strip():
            conditions.append(Verification.vid.ilike(f"%{query.strip()}%"))
        if due_before:
            conditions.append(Verification.sla_due_date.is_not(None))
            conditions.append(Verification.sla_due_date <= due_before)
        base = select(Verification).where(*conditions)
        total = await self._session.scalar(select(func.count()).select_from(base.subquery()))
        rows = (
            await self._session.execute(
                base.order_by(Verification.date_created.desc()).offset(offset).limit(limit)
            )
        ).scalars().all()
        return list(rows), int(total or 0)

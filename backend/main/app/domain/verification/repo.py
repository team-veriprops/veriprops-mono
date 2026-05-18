from datetime import datetime, timedelta
from typing import Dict, List, Optional, Type

from kink import inject
from sqlalchemy import func, select, case
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.verification.models import (
    CreateVerificationDto,
    QueryVerificationDto,
    SearchVerificationDto,
    UpdateVerificationDto,
    Verification,
)
from main.appodus_utils.db.repo import GenericRepo


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
        stmt = (
            select(Verification)
            .where(Verification.deleted.is_(False), Verification.vid == vid)
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_draft_for_customer(self, customer_id: str) -> Optional[Verification]:
        stmt = (
            select(Verification)
            .where(
                Verification.deleted.is_(False),
                Verification.customer_id == customer_id,
                Verification.status == "DRAFT",
            )
            .order_by(Verification.date_created.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_abandoned(self, older_than_hours: int = 24) -> List[Verification]:
        """Return verifications abandoned (no email sent yet, stale, has draft data)."""
        cutoff = datetime.utcnow() - timedelta(hours=older_than_hours)
        stmt = (
            select(Verification)
            .where(
                Verification.deleted.is_(False),
                Verification.status.in_(["DRAFT", "SUBMITTED"]),
                Verification.abandonment_email_sent_at.is_(None),
                Verification.draft_step > 0,
                func.coalesce(Verification.date_updated, Verification.date_created) < cutoff,
            )
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_status_for_customer(self, customer_id: str) -> Dict[str, int]:
        """Return a mapping of status → count for all non-deleted verifications of one customer."""
        stmt = (
            select(Verification.status, func.count(Verification.id).label("cnt"))
            .where(
                Verification.deleted.is_(False),
                Verification.customer_id == customer_id,
            )
            .group_by(Verification.status)
        )
        result = await self._session.execute(stmt)
        return {row.status: row.cnt for row in result}

    async def list_abandoned_for_customer(
        self, customer_id: str, older_than_hours: int = 24
    ) -> List[Verification]:
        """Return this customer's stale DRAFT/SUBMITTED verifications older than the cutoff."""
        cutoff = datetime.utcnow() - timedelta(hours=older_than_hours)
        stmt = (
            select(Verification)
            .where(
                Verification.deleted.is_(False),
                Verification.customer_id == customer_id,
                Verification.status.in_(["DRAFT", "SUBMITTED"]),
                Verification.draft_step > 0,
                func.coalesce(Verification.date_updated, Verification.date_created) < cutoff,
            )
            .order_by(Verification.date_updated.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_completed_vids_for_customer(self, customer_id: str) -> List[str]:
        """Return VIDs of all COMPLETED verifications for this customer."""
        stmt = (
            select(Verification.vid)
            .where(
                Verification.deleted.is_(False),
                Verification.customer_id == customer_id,
                Verification.status == "COMPLETED",
            )
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

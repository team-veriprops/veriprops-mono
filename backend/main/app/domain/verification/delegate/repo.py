"""Case-delegate data access."""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Type

from kink import inject
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.verification.delegate.models import (
    CaseDelegate,
    CreateCaseDelegateDto,
    QueryCaseDelegateDto,
    SearchCaseDelegateDto,
    UpdateCaseDelegateDto,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class CaseDelegateRepo(
    GenericRepo[
        CaseDelegate,
        CreateCaseDelegateDto,
        UpdateCaseDelegateDto,
        QueryCaseDelegateDto,
        SearchCaseDelegateDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[CaseDelegate] = CaseDelegate,
        query_dto: Type[QueryCaseDelegateDto] = QueryCaseDelegateDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def get_live_for_case(self, verification_id: str) -> Optional[CaseDelegate]:
        """The case's un-revoked delegate row, verified or not.

        "Live" rather than "active" on purpose: an authorization awaiting its OTP still
        occupies the one-per-case slot, so a buyer who nominates twice by mistake gets a
        clear refusal rather than two codes in flight to two numbers.
        """
        stmt = select(CaseDelegate).where(and_(
            CaseDelegate.deleted.is_(False),
            CaseDelegate.verification_id == verification_id,
            CaseDelegate.revoked_at.is_(None),
        ))
        return (await self._session.execute(stmt)).scalars().first()

    async def get_active_by_phone(self, phone_e164: str) -> Optional[CaseDelegate]:
        """The delegation this number holds, if any — verified and un-revoked only.

        The read behind the bot's second identity lookup. An unverified row answers
        nothing: someone who was nominated but never proved control of the number has no
        more standing than a stranger.
        """
        stmt = select(CaseDelegate).where(and_(
            CaseDelegate.deleted.is_(False),
            CaseDelegate.phone_e164 == phone_e164,
            CaseDelegate.verified_at.is_not(None),
            CaseDelegate.revoked_at.is_(None),
        ))
        return (await self._session.execute(stmt)).scalars().first()

    async def get_active_for_case(self, verification_id: str) -> Optional[CaseDelegate]:
        """The case's delegate for milestone delivery — verified and un-revoked.

        Resolved at send time, which is what makes §26.4.5's "revocation takes effect on
        the next event" fall out of the design rather than needing a sweep.
        """
        stmt = select(CaseDelegate).where(and_(
            CaseDelegate.deleted.is_(False),
            CaseDelegate.verification_id == verification_id,
            CaseDelegate.verified_at.is_not(None),
            CaseDelegate.revoked_at.is_(None),
        ))
        return (await self._session.execute(stmt)).scalars().first()

    def verify(self, delegate: CaseDelegate, at: datetime) -> CaseDelegate:
        """Mark the number proved — the moment visibility begins."""
        delegate.verified_at = at
        self._session.add(delegate)
        return delegate

    def revoke(self, delegate: CaseDelegate, reason: str, at: datetime) -> CaseDelegate:
        """End the delegation. The row is kept: who saw what, and until when, is the
        record the buyer may later want."""
        delegate.revoked_at = at
        delegate.revoked_reason = reason
        self._session.add(delegate)
        return delegate

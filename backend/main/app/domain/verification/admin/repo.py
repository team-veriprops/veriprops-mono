"""Admin verification repo — cross-customer filterable queries."""
from __future__ import annotations

from typing import List, Optional, Tuple, Type, TYPE_CHECKING

from kink import inject
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.verification.admin.models import (
    CreateVerificationNoteDto,
    QueryVerificationNoteDto,
    SearchVerificationNoteDto,
    UpdateVerificationNoteDto,
    VerificationNote,
)
from main.app.domain.verification.models import Verification
from main.app.domain.verification.property.models import Property
from main.appodus_utils.db.models import Page
from main.appodus_utils.db.repo import GenericRepo


@inject
class VerificationNoteRepo(
    GenericRepo[
        VerificationNote,
        CreateVerificationNoteDto,
        UpdateVerificationNoteDto,
        QueryVerificationNoteDto,
        SearchVerificationNoteDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[VerificationNote] = VerificationNote,
        query_dto: Type[QueryVerificationNoteDto] = QueryVerificationNoteDto,
    ):
        super().__init__(db, model, query_dto)

    async def list_for_verification(self, verification_id: str) -> List[VerificationNote]:
        stmt = (
            select(VerificationNote)
            .where(
                VerificationNote.deleted.is_(False),
                VerificationNote.verification_id == verification_id,
            )
            .order_by(VerificationNote.pinned.desc(), VerificationNote.date_created.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


@inject
class AdminVerificationRepo:
    """Cross-customer verification queries for admin use."""

    def __init__(self, db: AsyncSession):
        self._db = db

    @property
    def _session(self) -> AsyncSession:
        from main.appodus_utils.db.session import get_db_session_from_context
        return get_db_session_from_context()

    async def list_admin(
        self,
        *,
        status: Optional[str] = None,
        tier: Optional[str] = None,
        state: Optional[str] = None,
        lga: Optional[str] = None,
        vid: Optional[str] = None,
        page: int = 0,
        page_size: int = 25,
    ) -> Tuple[List[Verification], int]:
        from sqlalchemy import cast as sa_cast, String as SAString, text
        conditions = [Verification.deleted.is_(False)]
        if status:
            conditions.append(Verification.status == status)
        if tier:
            conditions.append(Verification.tier == tier)
        if vid:
            conditions.append(Verification.vid == vid)

        # State/LGA: subquery to get property_ids that match geo criteria
        if state or lga:
            prop_conditions = [Property.deleted.is_(False)]
            if state:
                prop_conditions.append(Property.state == state.upper())
            if lga:
                prop_conditions.append(Property.lga == lga)
            matching_prop_ids_q = (
                select(sa_cast(Property.id, SAString))
                .where(*prop_conditions)
                .scalar_subquery()
            )
            conditions.append(Verification.property_id.in_(matching_prop_ids_q))

        stmt = select(Verification).where(*conditions)
        count_stmt = select(func.count(Verification.id)).where(*conditions)

        total = await self._session.scalar(count_stmt) or 0
        offset = (page - 1) * page_size
        stmt = stmt.order_by(Verification.date_created.desc()).offset(offset).limit(page_size)
        result = await self._session.execute(stmt)
        return list(result.scalars().all()), total

    async def get_by_vid(self, vid: str) -> Optional[Verification]:
        stmt = (
            select(Verification)
            .where(Verification.deleted.is_(False), Verification.vid == vid)
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, verification_id: str) -> Optional[Verification]:
        stmt = (
            select(Verification)
            .where(Verification.deleted.is_(False), Verification.id == verification_id)
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

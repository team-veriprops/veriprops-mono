"""Admin note data access."""
from __future__ import annotations

from typing import List, Type

from kink import inject
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.verification.admin_note.models import (
    AdminNote,
    CreateAdminNoteDto,
    QueryAdminNoteDto,
    SearchAdminNoteDto,
    UpdateAdminNoteDto,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class AdminNoteRepo(
    GenericRepo[
        AdminNote,
        CreateAdminNoteDto,
        UpdateAdminNoteDto,
        QueryAdminNoteDto,
        SearchAdminNoteDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[AdminNote] = AdminNote,
        query_dto: Type[QueryAdminNoteDto] = QueryAdminNoteDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def list_for_verification(self, verification_id: str) -> List[AdminNote]:
        """Pinned notes first, then most-recent — the admin detail ordering."""
        stmt = (
            select(AdminNote)
            .where(
                AdminNote.deleted.is_(False),
                AdminNote.verification_id == verification_id,
            )
            .order_by(desc(AdminNote.pinned), desc(AdminNote.date_created))
        )
        return list((await self._session.execute(stmt)).scalars().all())

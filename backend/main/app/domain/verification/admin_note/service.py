"""Admin note service (PRD §6.6). Internal-only; never surfaced to customers/agents."""
from __future__ import annotations

from typing import List

from kink import inject

from main.app.domain.verification.admin_note.models import (
    AddAdminNoteDto,
    AdminNote,
    CreateAdminNoteDto,
)
from main.app.domain.verification.admin_note.repo import AdminNoteRepo
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class AdminNoteService:
    def __init__(self, admin_note_repo: AdminNoteRepo):
        self._repo = admin_note_repo

    async def add(self, verification_id: str, author_id: str, dto: AddAdminNoteDto) -> AdminNote:
        return await self._repo.create_return_model(CreateAdminNoteDto(
            verification_id=verification_id,
            author_id=author_id,
            category=dto.category,
            body=dto.body,
            pinned=dto.pinned,
        ))

    async def list_for_verification(self, verification_id: str) -> List[AdminNote]:
        return await self._repo.list_for_verification(verification_id)

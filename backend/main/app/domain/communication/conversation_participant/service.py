"""Conversation participant service — membership + read state (§N.3)."""
from __future__ import annotations

from typing import Optional

from kink import inject

from main.app.domain.communication.conversation_participant.models import (
    ConversationParticipant,
    CreateConversationParticipantDto,
)
from main.app.domain.communication.conversation_participant.repo import ConversationParticipantRepo
from main.appodus_utils import Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class ConversationParticipantService:
    def __init__(self, participant_repo: ConversationParticipantRepo):
        self._repo = participant_repo

    async def ensure_participant(
        self, conversation_id: str, user_id: str, role: Optional[str] = None
    ) -> ConversationParticipant:
        """Idempotently add a user to a thread (no-op if already a participant)."""
        existing = await self._repo.get_for(conversation_id, user_id)
        if existing:
            return existing
        return await self._repo.create_return_model(
            CreateConversationParticipantDto(
                conversation_id=conversation_id, user_id=user_id, role=role
            )
        )

    async def mark_read(self, conversation_id: str, user_id: str) -> None:
        """Stamp the viewer's ``last_read_at`` to now — clears the thread's unread badge.

        The timestamp is set on the attached ORM row (not via the update DTO path, which
        stringifies datetimes and asyncpg rejects for a timestamp column)."""
        participant = await self._repo.get_for(conversation_id, user_id)
        if participant is None:
            participant = await self.ensure_participant(conversation_id, user_id)
        participant.last_read_at = Utils.datetime_now()
        self._repo._session.add(participant)

    async def unread_conversation_count(self, user_id: str) -> int:
        """Number of the user's conversations with unread messages (Chat counter, §N.3)."""
        return await self._repo.unread_conversation_count(user_id)

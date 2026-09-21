"""Conversation participant service — membership + read state (§N.3)."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from kink import inject
from sqlalchemy.exc import IntegrityError

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
        self._participant_repo = participant_repo

    async def ensure_participant(
        self, conversation_id: str, user_id: str, role: Optional[str] = None
    ) -> ConversationParticipant:
        """Idempotently add a user to a thread (no-op if already a participant).

        Safe against a concurrent first open of the same thread: the unique index on live
        memberships makes the loser's insert fail, and it then returns the winner's row.
        """
        conversation_id, user_id = Utils.uuid_to_hex(conversation_id), str(user_id)
        existing = await self._participant_repo.get_for(conversation_id, user_id)
        if existing:
            return existing
        try:
            # A savepoint, so losing the race does not poison the caller's transaction.
            async with self._participant_repo._session.begin_nested():
                return await self._participant_repo.create_return_model(
                    CreateConversationParticipantDto(
                        conversation_id=conversation_id, user_id=user_id, role=role
                    )
                )
        except IntegrityError:
            winner = await self._participant_repo.get_for(conversation_id, user_id)
            if winner is None:
                raise
            return winner

    async def get_membership(
        self, conversation_id: str, user_id: str
    ) -> Optional[ConversationParticipant]:
        """The user's membership row — carries the visibility window a feed must respect."""
        return await self._participant_repo.get_for(conversation_id, user_id)

    async def mark_read(self, conversation_id: str, user_id: str) -> None:
        """Stamp the viewer's ``last_read_at`` to now — clears the thread's unread badge.

        The timestamp is set on the attached ORM row (not via the update DTO path, which
        stringifies datetimes and asyncpg rejects for a timestamp column)."""
        participant = await self._participant_repo.get_for(conversation_id, user_id)
        if participant is None:
            participant = await self.ensure_participant(conversation_id, user_id)
        participant.last_read_at = Utils.datetime_now()
        self._participant_repo._session.add(participant)

    async def advance_read(self, conversation_id: str, user_id: str, at: datetime) -> bool:
        """Move a member's ``last_read_at`` forward to *at*, when they read elsewhere.

        A WhatsApp read receipt, or the customer writing back on WhatsApp, means they have
        seen the thread up to *at* (D92). Never backwards — receipts arrive late — and only
        inside an open window: a released number's former owner, or a read from before they
        linked, is not theirs to count. Returns whether anything moved.
        """
        membership = await self._participant_repo.get_for(conversation_id, user_id)
        if membership is None or membership.is_read_only:
            return False
        if membership.visible_from is not None and at < membership.visible_from:
            return False
        if membership.last_read_at is not None and membership.last_read_at >= at:
            return False
        membership.last_read_at = at
        self._participant_repo._session.add(membership)
        return True

    async def unread_conversation_count(self, user_id: str) -> int:
        """Number of the user's conversations with unread messages (Chat counter, §N.3)."""
        return await self._participant_repo.unread_conversation_count(user_id)

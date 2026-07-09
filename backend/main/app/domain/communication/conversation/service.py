"""Conversation (thread) service (PRD §11.1).

Owns thread lifecycle: get-or-create the single thread of a channel for a verification
(or a user's general-support thread), the per-user conversation list with unread badges,
and the ``last_message_at`` bump when a message is delivered.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from kink import inject

from main.app.domain.communication.conversation.models import (
    Conversation,
    ConversationDto,
    ConversationType,
    CreateConversationDto,
)
from main.app.domain.communication.conversation.repo import ConversationRepo
from main.app.domain.communication.conversation_participant.repo import ConversationParticipantRepo
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import ResourceNotFoundException


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class ConversationService:
    def __init__(
        self,
        conversation_repo: ConversationRepo,
        participant_repo: ConversationParticipantRepo,
    ):
        self._conversation_repo = conversation_repo
        self._participants = participant_repo

    async def get_or_create_verification_thread(
        self,
        verification_id: str,
        conversation_type: ConversationType,
        created_by: str,
        subject: Optional[str] = None,
    ) -> Conversation:
        existing = await self._conversation_repo.get_for_verification(verification_id, conversation_type)
        if existing:
            return existing
        return await self._conversation_repo.create_return_model(
            CreateConversationDto(
                type=conversation_type,
                verification_id=verification_id,
                subject=subject,
                created_by=created_by,
            )
        )

    async def get_or_create_support_thread(self, user_id: str) -> Conversation:
        existing = await self._conversation_repo.get_general_support(user_id)
        if existing:
            return existing
        return await self._conversation_repo.create_return_model(
            CreateConversationDto(
                type=ConversationType.GENERAL_SUPPORT,
                verification_id=None,
                subject="General support",
                created_by=user_id,
            )
        )

    async def get_owned_participant(self, conversation_id: str, user_id: str) -> Conversation:
        """The thread, asserting the user is a participant — raises 404 otherwise (so a
        non-member cannot probe a thread's existence)."""
        participant = await self._participants.get_for(conversation_id, user_id)
        if participant is None:
            raise ResourceNotFoundException(resource="Conversation")
        convo = await self._conversation_repo.get_model(conversation_id)
        if convo is None or convo.deleted:
            raise ResourceNotFoundException(resource="Conversation")
        return convo

    async def touch(self, conversation_id: str, at: datetime) -> None:
        """Advance ``last_message_at`` to a delivered message's time (drives unread state).

        Set on the attached row rather than the update DTO path (datetime columns)."""
        convo = await self._conversation_repo.get_model(conversation_id)
        if convo is None:
            return
        convo.last_message_at = at
        self._conversation_repo._session.add(convo)

    async def list_for_user(self, user_id: str) -> List[ConversationDto]:
        """The user's threads (Chat conversation list, §N.3), each with its unread count."""
        memberships = await self._participants.list_for_user(user_id)
        by_conv = {m.conversation_id: m for m in memberships}
        conversations = await self._conversation_repo.list_by_ids(list(by_conv.keys()))
        result: List[ConversationDto] = []
        for convo in conversations:
            membership = by_conv.get(convo.id)
            unread = self._unread_for(convo, membership.last_read_at if membership else None)
            result.append(self._to_dto(convo, unread))
        return result

    async def list_for_admin(self, admin_id: str) -> List[ConversationDto]:
        """Admin shared inbox (§N.3): every verification thread, unread computed against this
        admin's own read state (a thread the admin has never opened reads as unread)."""
        threads = await self._conversation_repo.list_verification_threads()
        result: List[ConversationDto] = []
        for convo in threads:
            participant = await self._participants.get_for(convo.id, admin_id)
            unread = self._unread_for(convo, participant.last_read_at if participant else None)
            result.append(self._to_dto(convo, unread))
        return result

    async def unread_count_for_admin(self, admin_id: str) -> int:
        threads = await self._conversation_repo.list_verification_threads()
        count = 0
        for convo in threads:
            participant = await self._participants.get_for(convo.id, admin_id)
            if self._unread_for(convo, participant.last_read_at if participant else None):
                count += 1
        return count

    @staticmethod
    def _to_dto(convo: Conversation, unread: int) -> ConversationDto:
        return ConversationDto(
            id=convo.id,
            type=ConversationType(convo.type),
            verification_id=convo.verification_id,
            subject=convo.subject,
            last_message_at=convo.last_message_at,
            closed=convo.closed,
            unread=unread,
        )

    @staticmethod
    def _unread_for(convo: Conversation, last_read_at: Optional[datetime]) -> int:
        """1 if the thread has messages newer than the viewer last read, else 0 (the Chat
        counter counts *conversations* with unread, §N.3 — not individual messages)."""
        if convo.last_message_at is None:
            return 0
        if last_read_at is None or last_read_at < convo.last_message_at:
            return 1
        return 0

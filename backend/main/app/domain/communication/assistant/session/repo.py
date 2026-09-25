"""Assistant session data access."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Type

from kink import inject
from sqlalchemy import and_, desc, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import set_committed_value

from main.app.domain.communication.assistant.session.models import (
    AssistantSession,
    BotMode,
    CreateAssistantSessionDto,
    QueryAssistantSessionDto,
    SearchAssistantSessionDto,
    UpdateAssistantSessionDto,
)
from main.appodus_utils import Utils
from main.appodus_utils.db.repo import GenericRepo


@inject
class AssistantSessionRepo(
    GenericRepo[
        AssistantSession,
        CreateAssistantSessionDto,
        UpdateAssistantSessionDto,
        QueryAssistantSessionDto,
        SearchAssistantSessionDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[AssistantSession] = AssistantSession,
        query_dto: Type[QueryAssistantSessionDto] = QueryAssistantSessionDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def get_by_conversation(self, conversation_id: str) -> Optional[AssistantSession]:
        """The conversation's session, if the assistant has ever taken a turn on it."""
        stmt = select(AssistantSession).where(
            and_(
                AssistantSession.deleted.is_(False),
                AssistantSession.conversation_id == Utils.uuid_to_hex(conversation_id),
            )
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def get_by_phone(self, phone_e164: str) -> Optional[AssistantSession]:
        """The session of the WhatsApp conversation for this number — what an intake link,
        which names a number rather than a conversation, is redeemed against."""
        stmt = (
            select(AssistantSession)
            .where(
                and_(
                    AssistantSession.deleted.is_(False),
                    AssistantSession.phone_e164 == phone_e164,
                )
            )
            .order_by(desc(AssistantSession.date_created))
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def pending_conversation_ids(self, conversation_ids: List[str]) -> set[str]:
        """Which of these conversations have a web turn waiting for the intent model."""
        if not conversation_ids:
            return set()
        hex_ids = [Utils.uuid_to_hex(cid) for cid in conversation_ids]
        stmt = select(AssistantSession.conversation_id).where(
            and_(
                AssistantSession.deleted.is_(False),
                AssistantSession.conversation_id.in_(hex_ids),
                AssistantSession.pending_turn_message_id.is_not(None),
            )
        )
        return set((await self._session.execute(stmt)).scalars().all())

    async def claim_pending_turn(
        self, conversation_id: str, *, now: datetime, stale_before: datetime
    ) -> Optional[str]:
        """Claim this conversation's pending turn, returning the message it answers.

        One conditional UPDATE, so two requests racing for the same turn cannot both win:
        the database lets exactly one of them change ``turn_claimed_at``. A claim older than
        *stale_before* belonged to a request that died mid-turn and may be taken over.
        Returns ``None`` when there is nothing to claim or someone else holds it.
        """
        stmt = (
            update(AssistantSession)
            .where(
                and_(
                    AssistantSession.deleted.is_(False),
                    AssistantSession.conversation_id == Utils.uuid_to_hex(conversation_id),
                    AssistantSession.pending_turn_message_id.is_not(None),
                    or_(
                        AssistantSession.turn_claimed_at.is_(None),
                        AssistantSession.turn_claimed_at < stale_before,
                    ),
                )
            )
            .values(turn_claimed_at=now)
            .returning(AssistantSession.pending_turn_message_id)
        )
        return (await self._session.execute(stmt)).scalar()

    async def list_claimable_turns(self, *, waiting_before: datetime, stale_before: datetime, limit: int) -> List[str]:
        """Conversations whose pending turn nobody picked up — the sweep's work list.

        *waiting_before* leaves a just-marked turn to the customer's own second request,
        which is normally already on its way.
        """
        stmt = (
            select(AssistantSession.conversation_id)
            .where(
                and_(
                    AssistantSession.deleted.is_(False),
                    AssistantSession.pending_turn_message_id.is_not(None),
                    AssistantSession.pending_turn_at < waiting_before,
                    or_(
                        AssistantSession.turn_claimed_at.is_(None),
                        AssistantSession.turn_claimed_at < stale_before,
                    ),
                )
            )
            .order_by(AssistantSession.pending_turn_at)
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def count_unmatched(self, session: AssistantSession) -> int:
        """Count one missed turn in SQL and return the new run length.

        Two messages landing together are each a miss; counting them on the loaded row
        would let both write back the same total and the escalation would come a turn
        late. The loaded row is refreshed without being marked changed, so a later flush
        cannot write a stale count back.
        """
        stmt = (
            update(AssistantSession)
            .where(AssistantSession.id == self._ensure_uuid(session.id))
            .values(unmatched_count=func.coalesce(AssistantSession.unmatched_count, 0) + 1)
            .returning(AssistantSession.unmatched_count)
        )
        count = int((await self._session.execute(stmt)).scalar_one())
        set_committed_value(session, "unmatched_count", count)
        return count

    async def count_in_human_mode(self) -> int:
        """How many threads the assistant is currently silent on (D57).

        The §26.11 readiness signal that matters operationally: a count that only grows
        means agents are taking threads over and never handing them back, and every one
        of those customers is talking to nobody when the agent moves on.
        """
        stmt = select(func.count()).select_from(
            select(AssistantSession.id)
            .where(
                and_(
                    AssistantSession.deleted.is_(False),
                    AssistantSession.mode == BotMode.HUMAN.value,
                )
            )
            .subquery()
        )
        return int(await self._session.scalar(stmt) or 0)

    def save(self, session: AssistantSession) -> AssistantSession:
        """Persist edits made on an attached row.

        Session lifecycle is all datetime and nullable-field churn — clearing a flow,
        stamping a welcome — and the generic update path both drops ``None`` values and
        stringifies datetimes, so neither survives it. Mutating the attached object is
        the same reason `WhatsAppLinkRepo` sets its lifecycle fields directly.
        """
        self._session.add(session)
        return session

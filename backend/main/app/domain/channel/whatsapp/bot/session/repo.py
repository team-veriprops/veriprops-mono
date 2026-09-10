"""Bot session data access."""
from __future__ import annotations

from typing import Optional, Type

from kink import inject
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.channel.whatsapp.bot.session.models import (
    CreateWhatsAppBotSessionDto,
    QueryWhatsAppBotSessionDto,
    SearchWhatsAppBotSessionDto,
    BotMode,
    UpdateWhatsAppBotSessionDto,
    WhatsAppBotSession,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class WhatsAppBotSessionRepo(
    GenericRepo[
        WhatsAppBotSession,
        CreateWhatsAppBotSessionDto,
        UpdateWhatsAppBotSessionDto,
        QueryWhatsAppBotSessionDto,
        SearchWhatsAppBotSessionDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[WhatsAppBotSession] = WhatsAppBotSession,
        query_dto: Type[QueryWhatsAppBotSessionDto] = QueryWhatsAppBotSessionDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def get_by_phone(self, phone_e164: str) -> Optional[WhatsAppBotSession]:
        """This number's session, if it has ever written to us."""
        stmt = select(WhatsAppBotSession).where(
            and_(
                WhatsAppBotSession.deleted.is_(False),
                WhatsAppBotSession.phone_e164 == phone_e164,
            )
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def count_in_human_mode(self) -> int:
        """How many threads the bot is currently silent on (D57).

        The §26.11 readiness signal that matters operationally: a count that only grows
        means agents are taking threads over and never handing them back, and every one
        of those customers is talking to nobody when the agent moves on.
        """
        stmt = select(func.count()).select_from(
            select(WhatsAppBotSession.id)
            .where(
                and_(
                    WhatsAppBotSession.deleted.is_(False),
                    WhatsAppBotSession.mode == BotMode.HUMAN.value,
                )
            )
            .subquery()
        )
        return int(await self._session.scalar(stmt) or 0)

    def save(self, session: WhatsAppBotSession) -> WhatsAppBotSession:
        """Persist edits made on an attached row.

        Session lifecycle is all datetime and nullable-field churn — clearing a flow,
        stamping a welcome — and the generic update path both drops ``None`` values and
        stringifies datetimes, so neither survives it. Mutating the attached object is
        the same reason `WhatsAppLinkRepo` sets its lifecycle fields directly.
        """
        self._session.add(session)
        return session

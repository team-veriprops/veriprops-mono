"""Inbound WhatsApp message data access."""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Type

from kink import inject
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.channel.whatsapp.inbound.models import (
    CreateWhatsAppInboundMessageDto,
    QueryWhatsAppInboundMessageDto,
    SearchWhatsAppInboundMessageDto,
    UpdateWhatsAppInboundMessageDto,
    WhatsAppInboundMessage,
)
from main.appodus_utils.db.repo import GenericRepo
from main.appodus_utils.integrations.messaging.providers.whatsapp.inbound import InboundKind


@inject
class WhatsAppInboundMessageRepo(
    GenericRepo[
        WhatsAppInboundMessage,
        CreateWhatsAppInboundMessageDto,
        UpdateWhatsAppInboundMessageDto,
        QueryWhatsAppInboundMessageDto,
        SearchWhatsAppInboundMessageDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[WhatsAppInboundMessage] = WhatsAppInboundMessage,
        query_dto: Type[QueryWhatsAppInboundMessageDto] = QueryWhatsAppInboundMessageDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def get_by_wamid(self, wamid: str) -> Optional[WhatsAppInboundMessage]:
        """The recorded delivery for *wamid*, if we have already seen it.

        Deleted rows are included deliberately: a soft-deleted record still means the
        message was handled once, and a Meta redelivery must not resurrect it.
        """
        stmt = select(WhatsAppInboundMessage).where(WhatsAppInboundMessage.wamid == wamid)
        return (await self._session.execute(stmt)).scalars().first()

    async def last_received_at(self, from_phone: str) -> Optional[datetime]:
        """When this number last messaged us — the basis of Meta's 24-hour window.

        Read from the journal rather than a denormalised column so the window and the
        message history can never disagree about when the customer last wrote.
        """
        stmt = select(func.max(WhatsAppInboundMessage.received_at)).where(
            and_(
                WhatsAppInboundMessage.deleted.is_(False),
                WhatsAppInboundMessage.from_phone == from_phone,
            )
        )
        return (await self._session.execute(stmt)).scalar()

    async def count_by_kind(self, kind: InboundKind) -> int:
        """How many messages of *kind* arrived — the §7.10 voice-note volume metric."""
        stmt = select(func.count()).select_from(WhatsAppInboundMessage).where(
            and_(
                WhatsAppInboundMessage.deleted.is_(False),
                WhatsAppInboundMessage.kind == kind.value,
            )
        )
        return int((await self._session.execute(stmt)).scalar() or 0)

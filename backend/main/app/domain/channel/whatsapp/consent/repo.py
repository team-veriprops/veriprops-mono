"""WhatsApp consent data access."""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Type

from kink import inject
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.channel.whatsapp.consent.models import (
    CreateWhatsAppConsentDto,
    QueryWhatsAppConsentDto,
    SearchWhatsAppConsentDto,
    UpdateWhatsAppConsentDto,
    WhatsAppConsent,
    WhatsAppConsentKind,
    WhatsAppConsentSource,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class WhatsAppConsentRepo(
    GenericRepo[
        WhatsAppConsent,
        CreateWhatsAppConsentDto,
        UpdateWhatsAppConsentDto,
        QueryWhatsAppConsentDto,
        SearchWhatsAppConsentDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[WhatsAppConsent] = WhatsAppConsent,
        query_dto: Type[QueryWhatsAppConsentDto] = QueryWhatsAppConsentDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def get_by_user_id(self, user_id: str) -> Optional[WhatsAppConsent]:
        stmt = select(WhatsAppConsent).where(
            and_(WhatsAppConsent.deleted.is_(False), WhatsAppConsent.user_id == user_id)
        )
        return (await self._session.execute(stmt)).scalars().first()

    def apply(
        self,
        consent: WhatsAppConsent,
        kind: WhatsAppConsentKind,
        granted: bool,
        source: WhatsAppConsentSource,
        at: datetime,
    ) -> WhatsAppConsent:
        """Record one consent decision on the attached row.

        Stamps only the side that moved — a grant leaves the revocation timestamp in place
        and vice versa — because the pair *is* the history §7.8 asks us to keep. Mutating
        the attached object rather than going through the update path is deliberate: that
        path stringifies datetimes, which a timestamp column will not take.
        """
        prefix = "utility" if kind is WhatsAppConsentKind.UTILITY else "marketing"
        setattr(consent, f"{prefix}_granted_at" if granted else f"{prefix}_revoked_at", at)
        setattr(consent, f"{prefix}_source", source.value)
        self._session.add(consent)
        return consent

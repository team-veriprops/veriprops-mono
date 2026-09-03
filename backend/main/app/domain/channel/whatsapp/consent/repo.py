"""WhatsApp consent data access."""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Type

from kink import inject
from sqlalchemy import and_, func, or_, select
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

    async def count_granted(self) -> dict[str, int]:
        """How many accounts currently hold each §7.4.6 consent (§7.10).

        Granted-ness is derived here in SQL the same way `consent_granted` derives it in
        Python — a later grant beats an earlier revoke. Two expressions of one rule is one
        more than ideal, and the alternative is loading every consent row to count them;
        `test_whatsapp_consent_service.py` pins the two against each other.
        """
        def _live(granted_at, revoked_at):
            return and_(
                granted_at.is_not(None),
                or_(revoked_at.is_(None), revoked_at < granted_at),
            )

        stmt = select(
            func.count().filter(
                _live(WhatsAppConsent.utility_granted_at, WhatsAppConsent.utility_revoked_at)
            ),
            func.count().filter(
                _live(WhatsAppConsent.marketing_granted_at, WhatsAppConsent.marketing_revoked_at)
            ),
        ).where(WhatsAppConsent.deleted.is_(False))
        row = (await self._session.execute(stmt)).one()
        return {
            WhatsAppConsentKind.UTILITY.value: int(row[0] or 0),
            WhatsAppConsentKind.MARKETING.value: int(row[1] or 0),
        }

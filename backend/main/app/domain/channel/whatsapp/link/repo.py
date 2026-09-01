"""WhatsApp link data access."""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Type

from kink import inject
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.channel.whatsapp.link.models import (
    CreateWhatsAppLinkDto,
    QueryWhatsAppLinkDto,
    SearchWhatsAppLinkDto,
    UpdateWhatsAppLinkDto,
    WhatsAppLink,
    WhatsAppLinkStatus,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class WhatsAppLinkRepo(
    GenericRepo[
        WhatsAppLink,
        CreateWhatsAppLinkDto,
        UpdateWhatsAppLinkDto,
        QueryWhatsAppLinkDto,
        SearchWhatsAppLinkDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[WhatsAppLink] = WhatsAppLink,
        query_dto: Type[QueryWhatsAppLinkDto] = QueryWhatsAppLinkDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def get_by_user_id(self, user_id: str) -> Optional[WhatsAppLink]:
        """This account's link row, in whatever state it is in."""
        stmt = select(WhatsAppLink).where(
            and_(WhatsAppLink.deleted.is_(False), WhatsAppLink.user_id == user_id)
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def get_active_by_phone(self, phone_e164: str) -> Optional[WhatsAppLink]:
        """The account that owns *phone_e164*, if one has completed verification.

        `ACTIVE` only: a pending attempt is not a link, so someone who starts linking a
        number they do not control never appears here.
        """
        stmt = select(WhatsAppLink).where(
            and_(
                WhatsAppLink.deleted.is_(False),
                WhatsAppLink.phone_e164 == phone_e164,
                WhatsAppLink.status == WhatsAppLinkStatus.ACTIVE.value,
            )
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def get_any_by_phone(self, phone_e164: str) -> Optional[WhatsAppLink]:
        """Any live row holding *phone_e164* — including a pending attempt.

        Used at start-of-link to keep two accounts from racing on one number: the unique
        constraint would catch it, but a clear refusal beats a constraint violation.
        """
        stmt = select(WhatsAppLink).where(
            and_(WhatsAppLink.deleted.is_(False), WhatsAppLink.phone_e164 == phone_e164)
        )
        return (await self._session.execute(stmt)).scalars().first()

    def claim_number(self, link: WhatsAppLink, phone_e164: str, wa_id: str) -> WhatsAppLink:
        """Point an existing link row at a new number, back in `PENDING`.

        Mutates the attached row rather than going through the update path: that path
        drops `None` values and stringifies datetimes, neither of which this lifecycle
        can tolerate (see `release_number`).
        """
        link.phone_e164 = phone_e164
        link.wa_id = wa_id
        link.status = WhatsAppLinkStatus.PENDING.value
        link.linked_at = None
        link.revoked_at = None
        link.revoked_reason = None
        self._session.add(link)
        return link

    def activate(self, link: WhatsAppLink, at: datetime) -> WhatsAppLink:
        """Mark a confirmed link live — the moment the number starts meaning something."""
        link.status = WhatsAppLinkStatus.ACTIVE.value
        link.linked_at = at
        link.revoked_at = None
        link.revoked_reason = None
        self._session.add(link)
        return link

    def release_number(self, link: WhatsAppLink, reason: str, at: datetime) -> WhatsAppLink:
        """Revoke a link and free its number.

        Clearing `phone_e164` is the entire point: a retained number would keep its
        unique constraint held and lock that number out of every other account forever.
        """
        link.phone_e164 = None
        link.wa_id = None
        link.status = WhatsAppLinkStatus.REVOKED.value
        link.revoked_reason = reason
        link.revoked_at = at
        link.linked_at = None
        self._session.add(link)
        return link

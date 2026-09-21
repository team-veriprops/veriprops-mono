"""Meta template registry data access."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Type

from kink import inject
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.channel.whatsapp.template.models import (
    CreateWhatsAppTemplateDto,
    QueryWhatsAppTemplateDto,
    SearchWhatsAppTemplateDto,
    UpdateWhatsAppTemplateDto,
    WhatsAppTemplate,
    WhatsAppTemplateStatus,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class WhatsAppTemplateRepo(
    GenericRepo[
        WhatsAppTemplate,
        CreateWhatsAppTemplateDto,
        UpdateWhatsAppTemplateDto,
        QueryWhatsAppTemplateDto,
        SearchWhatsAppTemplateDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[WhatsAppTemplate] = WhatsAppTemplate,
        query_dto: Type[QueryWhatsAppTemplateDto] = QueryWhatsAppTemplateDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def get_by_name(self, name: str) -> Optional[WhatsAppTemplate]:
        stmt = select(WhatsAppTemplate).where(
            and_(WhatsAppTemplate.deleted.is_(False), WhatsAppTemplate.name == name)
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_all(self) -> List[WhatsAppTemplate]:
        stmt = select(WhatsAppTemplate).where(WhatsAppTemplate.deleted.is_(False))
        return list((await self._session.execute(stmt)).scalars().all())

    def apply_remote_state(
        self,
        row: WhatsAppTemplate,
        status: WhatsAppTemplateStatus,
        remote_id: Optional[str],
        rejection_reason: Optional[str],
        at: datetime,
    ) -> WhatsAppTemplate:
        """Write what Meta just said onto an existing row.

        Mutates the attached row rather than going through the update path: that path
        drops `None` values, and clearing a stale `rejection_reason` after a template is
        finally approved is exactly the kind of write that has to land.
        """
        row.status = status.value
        row.remote_id = remote_id
        row.rejection_reason = rejection_reason
        row.last_synced_at = at
        self._session.add(row)
        return row

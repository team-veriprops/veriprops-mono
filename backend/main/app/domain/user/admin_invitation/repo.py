from typing import Optional, Type

from kink import inject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.user.admin_invitation.models import (
    AdminInvitation,
    AdminInvitationStatus,
    CreateAdminInvitationDto,
    QueryAdminInvitationDto,
    SearchAdminInvitationDto,
    UpdateAdminInvitationDto,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class AdminInvitationRepo(
    GenericRepo[
        AdminInvitation,
        CreateAdminInvitationDto,
        UpdateAdminInvitationDto,
        QueryAdminInvitationDto,
        SearchAdminInvitationDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[AdminInvitation] = AdminInvitation,
        query_dto: Type[QueryAdminInvitationDto] = QueryAdminInvitationDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def get_by_token_hash(self, token_hash: str) -> Optional[AdminInvitation]:
        stmt = (
            select(AdminInvitation)
            .where(
                AdminInvitation.deleted.is_(False),
                AdminInvitation.token_hash == token_hash,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_pending_for_email(self, email_normalized: str) -> Optional[AdminInvitation]:
        stmt = (
            select(AdminInvitation)
            .where(
                AdminInvitation.deleted.is_(False),
                AdminInvitation.email_normalized == email_normalized,
                AdminInvitation.status == AdminInvitationStatus.PENDING.value,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

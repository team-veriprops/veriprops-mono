from typing import List, Optional, Type

from kink import inject
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.user.auth.session.models import (
    CreateDeviceSessionDto,
    CreatePasswordResetTokenDto,
    CreateSecurityEventDto,
    DeviceSession,
    PasswordResetToken,
    QueryDeviceSessionDto,
    QueryPasswordResetTokenDto,
    QuerySecurityEventDto,
    SearchDeviceSessionDto,
    SearchPasswordResetTokenDto,
    SearchSecurityEventDto,
    SecurityEvent,
    UpdateDeviceSessionDto,
    UpdatePasswordResetTokenDto,
    UpdateSecurityEventDto,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class DeviceSessionRepo(
    GenericRepo[
        DeviceSession,
        CreateDeviceSessionDto,
        UpdateDeviceSessionDto,
        QueryDeviceSessionDto,
        SearchDeviceSessionDto,
    ]
):
    def __init__(
            self,
            db: AsyncSession,
            model: Type[DeviceSession] = DeviceSession,
            query_dto: Type[QueryDeviceSessionDto] = QueryDeviceSessionDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def list_for_user(self, user_id: str) -> List[DeviceSession]:
        stmt = (
            select(DeviceSession)
            .where(
                DeviceSession.deleted.is_(False),
                DeviceSession.user_id == user_id,
                DeviceSession.revoked.is_(False),
            )
            .order_by(desc(DeviceSession.last_active_at))
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_token_hash(self, token_hash: str) -> Optional[DeviceSession]:
        stmt = select(DeviceSession).where(
            DeviceSession.deleted.is_(False),
            DeviceSession.refresh_token_hash == token_hash,
            DeviceSession.revoked.is_(False),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()


@inject
class SecurityEventRepo(
    GenericRepo[
        SecurityEvent,
        CreateSecurityEventDto,
        UpdateSecurityEventDto,
        QuerySecurityEventDto,
        SearchSecurityEventDto,
    ]
):
    def __init__(
            self,
            db: AsyncSession,
            model: Type[SecurityEvent] = SecurityEvent,
            query_dto: Type[QuerySecurityEventDto] = QuerySecurityEventDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def list_recent_for_user(self, user_id: str, limit: int = 50) -> List[SecurityEvent]:
        stmt = (
            select(SecurityEvent)
            .where(
                SecurityEvent.deleted.is_(False),
                SecurityEvent.user_id == user_id,
            )
            .order_by(desc(SecurityEvent.occurred_at))
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


@inject
class PasswordResetTokenRepo(
    GenericRepo[
        PasswordResetToken,
        CreatePasswordResetTokenDto,
        UpdatePasswordResetTokenDto,
        QueryPasswordResetTokenDto,
        SearchPasswordResetTokenDto,
    ]
):
    def __init__(
            self,
            db: AsyncSession,
            model: Type[PasswordResetToken] = PasswordResetToken,
            query_dto: Type[QueryPasswordResetTokenDto] = QueryPasswordResetTokenDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def get_by_token_hash(self, token_hash: str) -> Optional[PasswordResetToken]:
        stmt = select(PasswordResetToken).where(
            PasswordResetToken.deleted.is_(False),
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.consumed_at.is_(None),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

"""System configuration data access."""
from __future__ import annotations

from typing import List, Optional, Type

from kink import inject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.system_config.models import (
    CreateSystemConfigDto,
    QuerySystemConfigDto,
    SearchSystemConfigDto,
    SystemConfig,
    UpdateSystemConfigDto,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class SystemConfigRepo(
    GenericRepo[
        SystemConfig,
        CreateSystemConfigDto,
        UpdateSystemConfigDto,
        QuerySystemConfigDto,
        SearchSystemConfigDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[SystemConfig] = SystemConfig,
        query_dto: Type[QuerySystemConfigDto] = QuerySystemConfigDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def get_by_key(self, key: str) -> Optional[SystemConfig]:
        stmt = select(SystemConfig).where(
            SystemConfig.deleted.is_(False), SystemConfig.key == key
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_all(self) -> List[SystemConfig]:
        stmt = select(SystemConfig).where(SystemConfig.deleted.is_(False)).order_by(SystemConfig.key)
        return list((await self._session.execute(stmt)).scalars().all())

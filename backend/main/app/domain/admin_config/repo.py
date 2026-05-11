from __future__ import annotations

from typing import List, Optional, Type

from kink import inject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.admin_config.models import (
    AdminConfig,
    CreateAdminConfigDto,
    QueryAdminConfigDto,
    SearchAdminConfigDto,
    UpdateAdminConfigDto,
)
from main.appodus_utils.db.repo import GenericRepo
from main.appodus_utils.db.session import get_db_session_from_context


@inject
class AdminConfigRepo(
    GenericRepo[
        AdminConfig,
        CreateAdminConfigDto,
        UpdateAdminConfigDto,
        QueryAdminConfigDto,
        SearchAdminConfigDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[AdminConfig] = AdminConfig,
        query_dto: Type[QueryAdminConfigDto] = QueryAdminConfigDto,
    ):
        super().__init__(db, model, query_dto)

    async def get_by_key(self, key: str) -> Optional[AdminConfig]:
        stmt = (
            select(AdminConfig)
            .where(AdminConfig.deleted.is_(False), AdminConfig.key == key)
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self) -> List[AdminConfig]:
        stmt = select(AdminConfig).where(AdminConfig.deleted.is_(False)).order_by(AdminConfig.key)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

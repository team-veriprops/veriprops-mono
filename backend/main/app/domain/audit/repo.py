from datetime import datetime
from typing import List, Optional, Tuple, Type

from kink import inject
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.audit.models import (
    AuditLog,
    CreateAuditLogDto,
    QueryAuditLogDto,
    SearchAuditLogDto,
    UpdateAuditLogDto,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class AuditLogRepo(
    GenericRepo[
        AuditLog,
        CreateAuditLogDto,
        UpdateAuditLogDto,
        QueryAuditLogDto,
        SearchAuditLogDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[AuditLog] = AuditLog,
        query_dto: Type[QueryAuditLogDto] = QueryAuditLogDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def list_for_resource(
        self,
        resource_type: str,
        resource_id: str,
        offset: int,
        limit: int,
    ) -> Tuple[List[AuditLog], int]:
        base = (
            select(AuditLog)
            .where(
                AuditLog.deleted.is_(False),
                AuditLog.resource_type == resource_type,
                AuditLog.resource_id == resource_id,
            )
        )
        total = await self._session.scalar(
            select(func.count()).select_from(base.subquery())
        )
        rows = (
            await self._session.execute(
                base.order_by(AuditLog.occurred_at.asc()).offset(offset).limit(limit)
            )
        ).scalars().all()
        return list(rows), total or 0

    async def list_for_verification_pack(
        self,
        vid: str,
        task_ids: List[str],
    ) -> List[AuditLog]:
        conditions = [
            (AuditLog.resource_type == "VERIFICATION") & (AuditLog.resource_id == vid)
        ]
        if task_ids:
            conditions.append(
                (AuditLog.resource_type == "TASK") & (AuditLog.resource_id.in_(task_ids))
            )
        stmt = (
            select(AuditLog)
            .where(AuditLog.deleted.is_(False), or_(*conditions))
            .order_by(AuditLog.occurred_at.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_admin_actions(
        self,
        action_types: List[str],
        date_from: Optional[datetime],
        date_to: Optional[datetime],
        offset: int,
        limit: int,
    ) -> Tuple[List[AuditLog], int]:
        base = select(AuditLog).where(
            AuditLog.deleted.is_(False),
            AuditLog.action.in_(action_types),
        )
        if date_from:
            base = base.where(AuditLog.occurred_at >= date_from)
        if date_to:
            base = base.where(AuditLog.occurred_at <= date_to)
        total = await self._session.scalar(
            select(func.count()).select_from(base.subquery())
        )
        rows = (
            await self._session.execute(
                base.order_by(AuditLog.occurred_at.desc()).offset(offset).limit(limit)
            )
        ).scalars().all()
        return list(rows), total or 0

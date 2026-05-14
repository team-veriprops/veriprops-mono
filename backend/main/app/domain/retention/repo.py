"""Retention repo — DataErasureRequest CRUD + queries."""
from __future__ import annotations

from typing import List, Optional, Tuple, Type

from kink import inject
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.retention.models import (
    DataErasureRequest,
    CreateErasureRequestDto,
    UpdateErasureRequestDto,
    QueryErasureRequestDto,
    SearchErasureRequestDto,
    ErasureStatus,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class DataErasureRequestRepo(
    GenericRepo[
        DataErasureRequest,
        CreateErasureRequestDto,
        UpdateErasureRequestDto,
        QueryErasureRequestDto,
        SearchErasureRequestDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[DataErasureRequest] = DataErasureRequest,
        query_dto: Type[QueryErasureRequestDto] = QueryErasureRequestDto,
    ):
        super().__init__(db, model, query_dto)

    async def get_active_for_user(self, user_id: str) -> Optional[DataErasureRequest]:
        """Return any PENDING or APPROVED request for the user (one active at a time)."""
        stmt = select(DataErasureRequest).where(
            DataErasureRequest.deleted.is_(False),
            DataErasureRequest.user_id == user_id,
            DataErasureRequest.status.in_([ErasureStatus.PENDING.value, ErasureStatus.APPROVED.value]),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_latest_for_user(self, user_id: str) -> Optional[DataErasureRequest]:
        """Return the most recent erasure request for the user regardless of status."""
        stmt = (
            select(DataErasureRequest)
            .where(
                DataErasureRequest.deleted.is_(False),
                DataErasureRequest.user_id == user_id,
            )
            .order_by(DataErasureRequest.requested_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_status(
        self,
        status: Optional[str],
        offset: int,
        limit: int,
    ) -> Tuple[List[DataErasureRequest], int]:
        base = DataErasureRequest.deleted.is_(False)
        filters = [base]
        if status:
            filters.append(DataErasureRequest.status == status)

        count_stmt = select(func.count()).select_from(DataErasureRequest).where(*filters)
        total = (await self._session.execute(count_stmt)).scalar_one()

        stmt = (
            select(DataErasureRequest)
            .where(*filters)
            .order_by(DataErasureRequest.requested_at.desc())
            .offset(offset)
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return list(rows), total

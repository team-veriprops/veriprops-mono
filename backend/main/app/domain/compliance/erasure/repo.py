"""Data-erasure request data access."""
from __future__ import annotations

from typing import List, Optional, Tuple, Type

from kink import inject
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.core.state.status import ErasureRequestState
from main.app.domain.compliance.erasure.models import (
    CreateDataErasureRequestDto,
    DataErasureRequest,
    QueryDataErasureRequestDto,
    SearchDataErasureRequestDto,
    UpdateDataErasureRequestDto,
)
from main.appodus_utils.db.repo import GenericRepo

# A subject can have at most one request that is still in flight.
_OPEN_STATES = (ErasureRequestState.PENDING.value, ErasureRequestState.APPROVED.value)


@inject
class DataErasureRequestRepo(
    GenericRepo[
        DataErasureRequest,
        CreateDataErasureRequestDto,
        UpdateDataErasureRequestDto,
        QueryDataErasureRequestDto,
        SearchDataErasureRequestDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[DataErasureRequest] = DataErasureRequest,
        query_dto: Type[QueryDataErasureRequestDto] = QueryDataErasureRequestDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def get_open_for_user(self, subject_user_id: str) -> Optional[DataErasureRequest]:
        stmt = select(DataErasureRequest).where(
            DataErasureRequest.deleted.is_(False),
            DataErasureRequest.subject_user_id == subject_user_id,
            DataErasureRequest.status.in_(_OPEN_STATES),
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_for_user(self, subject_user_id: str) -> List[DataErasureRequest]:
        stmt = (
            select(DataErasureRequest)
            .where(
                DataErasureRequest.deleted.is_(False),
                DataErasureRequest.subject_user_id == subject_user_id,
            )
            .order_by(desc(DataErasureRequest.date_created))
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def page_by_status(
        self, status: Optional[str], offset: int, limit: int
    ) -> Tuple[List[DataErasureRequest], int]:
        base = select(DataErasureRequest).where(DataErasureRequest.deleted.is_(False))
        if status:
            base = base.where(DataErasureRequest.status == status)
        total = await self._session.scalar(select(func.count()).select_from(base.subquery()))
        rows = (
            await self._session.execute(
                base.order_by(desc(DataErasureRequest.date_created)).offset(offset).limit(limit)
            )
        ).scalars().all()
        return list(rows), int(total or 0)

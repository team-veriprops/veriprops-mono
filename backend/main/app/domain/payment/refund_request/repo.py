"""Refund request data access."""
from __future__ import annotations

from typing import List, Optional, Tuple, Type

from kink import inject
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.payment.refund_request.models import (
    CreateRefundRequestDto,
    QueryRefundRequestDto,
    RefundRequest,
    RefundRequestStatus,
    RefundSource,
    SearchRefundRequestDto,
    UpdateRefundRequestDto,
)
from main.app.domain.verification.models import Verification
from main.appodus_utils.db.db_utils import hex_ref
from main.appodus_utils.db.repo import GenericRepo


@inject
class RefundRequestRepo(
    GenericRepo[
        RefundRequest,
        CreateRefundRequestDto,
        UpdateRefundRequestDto,
        QueryRefundRequestDto,
        SearchRefundRequestDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[RefundRequest] = RefundRequest,
        query_dto: Type[QueryRefundRequestDto] = QueryRefundRequestDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def get_pending_for_verification(self, verification_id: str) -> Optional[RefundRequest]:
        stmt = select(RefundRequest).where(
            RefundRequest.deleted.is_(False),
            RefundRequest.verification_id == verification_id,
            RefundRequest.status == RefundRequestStatus.PENDING.value,
            RefundRequest.source != RefundSource.LATE_CHARGE.value,
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def page_with_vid(
        self, page: int, page_size: int, status: Optional[RefundRequestStatus],
    ) -> Tuple[List[Tuple[RefundRequest, str]], int]:
        """Requests with their case's VID. Pending ones oldest first (the queue's order);
        a decided list newest first (the record)."""
        criteria = [RefundRequest.deleted.is_(False)]
        if status is not None:
            criteria.append(RefundRequest.status == status.value)
        joined = (
            select(RefundRequest, Verification.vid)
            .join(Verification, hex_ref(Verification.id) == RefundRequest.verification_id)
            .where(*criteria)
        )
        order = (
            RefundRequest.date_created.asc() if status == RefundRequestStatus.PENDING
            else RefundRequest.date_created.desc()
        )
        total = await self._session.scalar(select(func.count()).select_from(joined.subquery()))
        rows = await self._session.execute(joined.order_by(order).offset(page * page_size).limit(page_size))
        return [tuple(row) for row in rows.all()], int(total or 0)

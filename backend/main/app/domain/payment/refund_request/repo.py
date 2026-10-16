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


# Finance's refund-request list: the columns a client may sort by.
REFUND_REQUEST_SORTABLE = frozenset({"amount_minor", "status", "date_created"})


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
        self, page: int, page_size: int, status: Optional[RefundRequestStatus], order_by: Optional[str] = None,
    ) -> Tuple[List[Tuple[RefundRequest, str]], int, str]:
        """Requests with their case's VID, plus the sort applied. Without a client *order_by*,
        pending ones come oldest first (the queue's order) and a decided list newest first (the record)."""
        criteria = [RefundRequest.deleted.is_(False)]
        if status is not None:
            criteria.append(RefundRequest.status == status.value)
        joined = (
            select(RefundRequest, Verification.vid)
            .join(Verification, hex_ref(Verification.id) == RefundRequest.verification_id)
            .where(*criteria)
        )
        default = "dateCreated asc" if status == RefundRequestStatus.PENDING else "dateCreated desc"
        applied, order = self._db_utils.client_order_by(order_by, REFUND_REQUEST_SORTABLE, default)
        total = await self._session.scalar(select(func.count()).select_from(joined.subquery()))
        rows = await self._session.execute(joined.order_by(*order).offset(page * page_size).limit(page_size))
        return [tuple(row) for row in rows.all()], int(total or 0), applied

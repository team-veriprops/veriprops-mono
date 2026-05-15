from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger

from typing import List, Optional

from kink import di, inject

from main.app.domain.broadcast.models import (
    Broadcast,
    BroadcastAudience,
    BroadcastDto,
    BroadcastStatus,
    CreateBroadcastDto,
    PreviewBroadcastDto,
    ScheduleBroadcastDto,
    UpdateBroadcastDto,
)
from main.app.domain.broadcast.repo import BroadcastRepo
from main.appodus_utils import Utils
from main.appodus_utils.db.models import Page, PaginationMeta
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import (
    InvalidResourceStateException,
    ResourceNotFoundException,
    ValidationException,
)

logger: Logger = di["logger"]

@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class BroadcastService:
    def __init__(self, repo: BroadcastRepo):
        self._repo = repo

    async def list_broadcasts(self, page: int = 0, page_size: int = 25) -> Page[BroadcastDto]:
        rows, total = await self._repo.list_all(page, page_size)
        items = [self._to_dto(r) for r in rows]
        meta = PaginationMeta(page=page, page_size=page_size, count=len(items), total=total)
        return Page[BroadcastDto](items=items, meta=meta)

    async def get(self, broadcast_id: str) -> BroadcastDto:
        row = await self._repo.get_model(broadcast_id)
        if row is None:
            raise ResourceNotFoundException(resource="Broadcast")
        return self._to_dto(row)

    async def create(self, dto: CreateBroadcastDto, admin_id: str) -> BroadcastDto:
        create_dto = CreateBroadcastDto(**{**dto.model_dump(), "created_by": admin_id})
        row = await self._repo.create_return_model(create_dto)
        return self._to_dto(row)

    async def update(self, broadcast_id: str, dto: UpdateBroadcastDto, admin_id: str) -> BroadcastDto:
        row = await self._repo.get_model(broadcast_id)
        if row is None:
            raise ResourceNotFoundException(resource="Broadcast")
        if row.status not in (BroadcastStatus.DRAFT.value, BroadcastStatus.SCHEDULED.value):
            raise InvalidResourceStateException(resource="Broadcast", message="Can only edit DRAFT or SCHEDULED broadcasts")
        updated = await self._repo.update_return_model(broadcast_id, dto)
        return self._to_dto(updated)

    async def schedule(self, broadcast_id: str, dto: ScheduleBroadcastDto, admin_id: str) -> BroadcastDto:
        row = await self._repo.get_model(broadcast_id)
        if row is None:
            raise ResourceNotFoundException(resource="Broadcast")
        if row.status != BroadcastStatus.DRAFT.value:
            raise InvalidResourceStateException(resource="Broadcast", message="Only DRAFT broadcasts can be scheduled")
        now = Utils.datetime_now().replace(tzinfo=None)
        if dto.scheduled_at.replace(tzinfo=None) <= now:
            raise ValidationException(message="scheduled_at must be in the future")
        await self._repo.update(broadcast_id, UpdateBroadcastDto(
            status=BroadcastStatus.SCHEDULED,
            scheduled_at=dto.scheduled_at,
        ))
        updated = await self._repo.get_model(broadcast_id)
        return self._to_dto(updated)

    async def cancel(self, broadcast_id: str, admin_id: str) -> BroadcastDto:
        row = await self._repo.get_model(broadcast_id)
        if row is None:
            raise ResourceNotFoundException(resource="Broadcast")
        if row.status not in (BroadcastStatus.DRAFT.value, BroadcastStatus.SCHEDULED.value):
            raise InvalidResourceStateException(resource="Broadcast", message="Cannot cancel a sent or sending broadcast")
        await self._repo.update(broadcast_id, UpdateBroadcastDto(status=BroadcastStatus.CANCELLED))
        updated = await self._repo.get_model(broadcast_id)
        return self._to_dto(updated)

    async def preview(self, broadcast_id: str) -> PreviewBroadcastDto:
        row = await self._repo.get_model(broadcast_id)
        if row is None:
            raise ResourceNotFoundException(resource="Broadcast")
        count = await self._count_recipients(BroadcastAudience(row.audience))
        return PreviewBroadcastDto(
            subject=row.subject,
            body_text=row.body_text,
            body_html=row.body_html,
            audience=BroadcastAudience(row.audience),
            estimated_recipients=count,
        )

    async def send_now(self, broadcast_id: str, admin_id: str) -> BroadcastDto:
        row = await self._repo.get_model(broadcast_id)
        if row is None:
            raise ResourceNotFoundException(resource="Broadcast")
        if row.status not in (BroadcastStatus.DRAFT.value, BroadcastStatus.SCHEDULED.value):
            raise InvalidResourceStateException(resource="Broadcast", message="Broadcast cannot be sent in its current state")

        await self._repo.update(broadcast_id, UpdateBroadcastDto(status=BroadcastStatus.SENDING))
        recipient_ids = await self._resolve_recipients(BroadcastAudience(row.audience))

        try:
            from main.app.domain.broadcast.messages import BroadcastMessages
            msg_svc: BroadcastMessages = di[BroadcastMessages]
            sent = 0
            for uid in recipient_ids:
                try:
                    await msg_svc.send_broadcast(uid, row.subject, row.body_html or row.body_text)
                    sent += 1
                except Exception:
                    pass
        except Exception:
            sent = 0

        await self._repo.update(broadcast_id, UpdateBroadcastDto(
            status=BroadcastStatus.SENT,
            sent_at=Utils.datetime_now(),
            total_recipients=len(recipient_ids),
            sent_count=sent,
        ))
        updated = await self._repo.get_model(broadcast_id)
        return self._to_dto(updated)

    async def _count_recipients(self, audience: BroadcastAudience) -> int:
        return len(await self._resolve_recipients(audience))

    async def _resolve_recipients(self, audience: BroadcastAudience) -> List[str]:
        try:
            return await self._repo.get_broadcast_user_ids(audience=audience)
        except Exception as e:
            logger.error("Error resolving broadcast recipients: {}", e)
            return []

    @staticmethod
    def _to_dto(row: Broadcast) -> BroadcastDto:
        return BroadcastDto(
            id=str(row.id),
            subject=row.subject,
            body_text=row.body_text,
            body_html=row.body_html,
            audience=BroadcastAudience(row.audience),
            channels=row.channels,
            status=BroadcastStatus(row.status) if row.status is not None else BroadcastStatus.DRAFT,
            scheduled_at=row.scheduled_at,
            sent_at=row.sent_at,
            created_by=row.created_by,
            total_recipients=row.total_recipients,
            sent_count=row.sent_count,
            date_created=row.date_created,
            date_updated=row.date_updated,
        )

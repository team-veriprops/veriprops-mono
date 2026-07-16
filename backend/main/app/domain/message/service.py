from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger

from datetime import datetime
from typing import Optional

from kink import inject, di

from main.appodus_utils import Page
from main.app.domain.message.models import QueryMessageDto, _UpdateMessageDto, SearchMessageDto, UpsertMessageDto
from main.app.domain.message.repo import MessageRepo
from main.app.domain.message.validator import MessageValidator
from main.appodus_utils.integrations.messaging.models import MessageStatus
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional, TransactionSessionPolicy

logger: Logger = di['logger']


# ALWAYS_NEW: message rows record an external side effect that has already
# happened (an email/SMS handed to a provider), so bookkeeping must commit
# independently of the caller's transaction — a request rollback must not erase
# the audit of a delivered message. It also keeps concurrent send_bulk branches
# and post-request dispatch contexts off the shared request session.
@inject
@decorate_all_methods(transactional(session_policy=TransactionSessionPolicy.ALWAYS_NEW),
                      exclude=['__init__'], exclude_startswith='_')
@decorate_all_methods(method_trace_logger, exclude=['__init__'], exclude_startswith='_')
class MessageService:
    def __init__(self, message_repo: MessageRepo, message_validator: MessageValidator):
        self._message_repo = message_repo
        self._message_validator = message_validator

    async def create_message(self, message: UpsertMessageDto) -> QueryMessageDto:
        # Column-filtered create: the Upsert DTO carries wire-only fields (sandbox_mode)
        # the stock GenericRepo create path would TypeError on.
        row = await self._message_repo.create_from_upsert(message)
        # Validate from a plain dict — the CamelModel before-validator coerces the
        # UUID primary key to its hex form only on dict input (from_attributes
        # bypasses it and the UUID then fails the str-typed id field).
        data = {column.key: getattr(row, column.key) for column in row.__table__.columns}
        return QueryMessageDto.model_validate(data)

    async def get_message_by_id(self, message_id: str) -> Optional[QueryMessageDto]:
        await self._message_validator.should_exist_by_id(message_id)
        return await self._message_repo.get(message_id)

    async def update_message(self, message_id: str, payload: UpsertMessageDto) -> QueryMessageDto:
        await self._message_validator.should_exist_by_id(message_id)
        return await self._message_repo.update(message_id, payload)

    async def update_message_status(self, message_id: str, status: MessageStatus, error: str = None) -> bool:
        await self._message_validator.should_exist_by_id(message_id)
        obj_in = _UpdateMessageDto(status=status, error=error)
        await self._message_repo.update(message_id, obj_in.model_dump(exclude_none=True))

        return True

    async def update_message_sent(self, message_id: str, sent_at: datetime, result: UpsertMessageDto) -> bool:
        await self._message_validator.should_exist_by_id(message_id)
        obj_in = _UpdateMessageDto(
            status=MessageStatus.SENT,
            sent_at=sent_at,
            provider=result.provider,
            provider_id=result.provider_id)
        await self._message_repo.update(message_id, obj_in.model_dump(exclude_none=True))

        return True

    async def update_message_delivered(self, message_id: str, delivered_at: datetime) -> bool:
        await self._message_validator.should_exist_by_id(message_id)
        obj_in = _UpdateMessageDto(status=MessageStatus.DELIVERED, delivered_at=delivered_at)
        await self._message_repo.update(message_id, obj_in.model_dump(exclude_none=True))

        return True

    async def schedule_message_retry(self, message_id: str, retry_count: int,
                                     next_retry_at: datetime, error: str) -> bool:
        """Mark a failed dispatch as awaiting re-dispatch by the retry sweep."""
        await self._message_validator.should_exist_by_id(message_id)
        obj_in = _UpdateMessageDto(status=MessageStatus.RETRYING, retry_count=retry_count,
                                   next_retry_at=next_retry_at, error=error)
        await self._message_repo.update(message_id, obj_in.model_dump(exclude_none=True))

        return True

    async def mark_message_failed(self, message_id: str, error: str) -> bool:
        """Permanent failure — the retry sweep never picks the message up again."""
        return await self.update_message_status(message_id, MessageStatus.FAILED, error)

    async def get_pending_messages(self, limit: int = 100) -> Page[QueryMessageDto]:
        page_size = limit
        search_dto = SearchMessageDto(page=0, page_size=page_size,
                                      status=MessageStatus.PENDING,
                                      order_by="priority, date_created",
                                      )

        return await self._message_repo.get_page(search_dto)

    async def get_retry_ready_messages(self, ready_before: datetime, limit: int = 100) -> Page[QueryMessageDto]:
        """RETRYING messages whose next_retry_at has passed — the retry-sweep batch.
        The retry threshold is enforced at scheduling time, not here."""
        search_dto = SearchMessageDto(page=0, page_size=limit,
                                      status=MessageStatus.RETRYING,
                                      next_retry_at=ready_before,
                                      order_by="next_retry_at",
                                      where="next_retry_at <= "
                                      )

        return await self._message_repo.get_page(search_dto)

    async def delete_processed(self, older_than: datetime) -> int:
        search_dto = SearchMessageDto(page=0, page_size=100,
                                      status=MessageStatus.DELIVERED,
                                      date_updated=older_than,
                                      where="date_updated <= "
                                      )

        return await self._message_repo.soft_delete_by_criterion(search_dto)

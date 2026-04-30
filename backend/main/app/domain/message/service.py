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
from main.appodus_utils.decorators.transactional import transactional

logger: Logger = di['logger']


@inject
@decorate_all_methods(transactional(), exclude=['__init__'], exclude_startswith='_')
@decorate_all_methods(method_trace_logger, exclude=['__init__'], exclude_startswith='_')
class MessageService:
    def __init__(self, message_repo: MessageRepo, message_validator: MessageValidator):
        self._message_repo = message_repo
        self._message_validator = message_validator

    async def create_message(self, message: UpsertMessageDto) -> QueryMessageDto:
        return await self._message_repo.create(message)

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
        obj_in = _UpdateMessageDto(status=MessageStatus.SENT, delivered_at=delivered_at)
        await self._message_repo.update(message_id, obj_in.model_dump(exclude_none=True))

        return True

    async def get_pending_messages(self, limit: int = 100) -> Page[QueryMessageDto]:
        page_size = limit
        search_dto = SearchMessageDto(page=0, page_size=page_size,
                                      status=MessageStatus.PENDING,
                                      order_by="priority, created_at",
                                      )

        return await self._message_repo.get_page(search_dto)

    async def get_failed_messages(self, max_retries: int, older_than: datetime) -> Page[QueryMessageDto]:
        page_size = 100
        search_dto = SearchMessageDto(page=0, page_size=page_size,
                                      status=MessageStatus.FAILED,
                                      retry_count=max_retries,
                                      created_at=older_than,
                                      order_by="retry_count, created_at",
                                      where="retry_count < AND created_at < "
                                      )

        return await self._message_repo.get_page(search_dto)

    async def delete_processed(self, older_than: datetime) -> int:
        search_dto = SearchMessageDto(page=0, page_size=100,
                                      status=MessageStatus.DELIVERED,
                                      date_updated=older_than,
                                      where="date_updated <= "
                                      )

        return await self._message_repo.soft_delete_by_criterion(search_dto)

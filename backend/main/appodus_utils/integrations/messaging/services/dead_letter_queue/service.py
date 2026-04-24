from datetime import datetime
from logging import Logger
from typing import Optional

from kink import inject, di

from main.appodus_utils import Page
from main.appodus_utils.integrations.messaging.services.dead_letter_queue.models import CreateDLQDto, QueryDLQDto, SearchDLQDto, \
    _UpdateDLQDto, DLQStatus
from main.appodus_utils.integrations.messaging.services.dead_letter_queue.repo import DLQRepo
from main.appodus_utils.integrations.messaging.services.dead_letter_queue.validator import DLQValidator
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional

logger: Logger = di['logger']


@inject
@decorate_all_methods(transactional(), exclude=['__init__'], exclude_startswith=['_'])
@decorate_all_methods(method_trace_logger, exclude=['__init__'], exclude_startswith=['_'])
class DLQService:
    def __init__(self, dLq_repo: DLQRepo, dLq_validator: DLQValidator):
        self._dLq_repo = dLq_repo
        self._dLq_validator = dLq_validator

    async def create(self, entry_data: CreateDLQDto) -> QueryDLQDto:
        return await self._dLq_repo.create(entry_data)

    async def get_by_id(self, entry_id: str) -> Optional[QueryDLQDto]:
        await self._dLq_validator.should_exist_by_id(entry_id)
        return await self._dLq_repo.get(entry_id)

    async def get_ready_for_retry(self, before: datetime, max_batch_size: int) -> Page[QueryDLQDto]:
        page_size = max_batch_size
        search_dto = SearchDLQDto(page=0, page_size=page_size,
                                  status=DLQStatus.PENDING,
                                  next_retry_at=before,
                                  order_by="next_retry_at",
                                  where="next_retry_at <= "
                                  )

        return await self._dLq_repo.get_page(search_dto)

    async def update_status(self, entry_id: str, status: DLQStatus) -> bool:
        await self._dLq_validator.should_exist_by_id(entry_id)
        obj_in = _UpdateDLQDto(status=status)
        await self._dLq_repo.update(entry_id, obj_in.model_dump(exclude_none=True))

        return True

    async def increment_attempt(self, entry_id: str) -> int:
        await self._dLq_validator.should_exist_by_id(entry_id)

        existing_value = await self._dLq_repo.get_model(entry_id, "attempts")

        new_attempts = int(existing_value["attempts"]) + 1

        obj_in = _UpdateDLQDto(attempts=new_attempts)
        await self._dLq_repo.update(entry_id, obj_in.model_dump(exclude_none=True))

        return new_attempts

    async def schedule_retry(self, entry_id: str, attempts: int, next_retry_at: datetime) -> bool:
        await self._dLq_validator.should_exist_by_id(entry_id)
        obj_in = _UpdateDLQDto(attempts=attempts, next_retry_at=next_retry_at, status=DLQStatus.PENDING)
        await self._dLq_repo.update(entry_id, obj_in.model_dump(exclude_none=True))

        return True

    async def mark_as_processed(self, entry_id: str) -> bool:
        return await self.update_status(entry_id, status=DLQStatus.PROCESSED)

    async def mark_as_failed(self, entry_id: str) -> bool:
        return await self.update_status(entry_id, status=DLQStatus.FAILED)

    async def delete_processed(self, older_than: datetime) -> int:
        search_dto = SearchDLQDto(page=0, page_size=100,
                                  status=DLQStatus.PROCESSED,
                                  date_updated=older_than,
                                  where="date_updated <= "
                                  )

        return await self._dLq_repo.soft_delete_by_criterion(search_dto)

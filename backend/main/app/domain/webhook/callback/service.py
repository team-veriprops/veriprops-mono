from logging import Logger

from kink import di, inject

from main.appodus_utils import Page
from main.app.domain.webhook.callback.model import CreateCallbackDto, QueryCallbackDto, SearchCallbackDto, \
    _UpdateCallbackDto
from main.app.domain.webhook.callback.repo import CallbackRepo
from main.app.domain.webhook.callback.validator import CallbackValidator
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional

logger: Logger = di['logger']


@inject
@decorate_all_methods(transactional(), exclude=['__init__'], exclude_startswith='_')
@decorate_all_methods(method_trace_logger, exclude=['__init__'], exclude_startswith='_')
class CallbackService:
    def __init__(self, callback_repo: CallbackRepo, callback_validator: CallbackValidator):
        self._callback_repo = callback_repo
        self._callback_validator = callback_validator

    async def create_callback(self, obj_in: CreateCallbackDto) -> QueryCallbackDto:
        return await self._callback_repo.create(obj_in)

    async def get_callback(self, callback_id: str) -> QueryCallbackDto:
        await self._callback_validator.should_exist_by_id(callback_id)
        return await self._callback_repo.get(callback_id)

    async def get_callback_page(self, search_dto: SearchCallbackDto) -> Page[QueryCallbackDto]:
        return await self._callback_repo.get_page(search_dto=search_dto)

    async def update_callback__handled(self, callback_id: str) -> bool:
        await self._callback_validator.should_exist_by_id(callback_id)
        obj_in = _UpdateCallbackDto(handled=True)
        await self._callback_repo.update(callback_id, obj_in.model_dump(exclude_none=True))

        return True

    async def update_callback__handle_time(self, obj_in: CreateCallbackDto) -> bool:
        search_dto = SearchCallbackDto(
            query_fields="id",
            platform=obj_in.platform,
            event_type=obj_in.event_type,
            external_id=obj_in.external_id,
            deleted=False,
            handled=False,
            page_size=1,
            page=0
        )
        callbacks = await self._callback_repo.get_by_criterion(search_dto=search_dto)
        if callbacks and len(callbacks) > 0:
            callback_id = callbacks[0].id

            obj_in = _UpdateCallbackDto(
                handle_from_time=obj_in.handle_from_time,
                payload=obj_in.payload,
            )
            await self._callback_repo.update(callback_id, obj_in.model_dump(exclude_none=True))

            return True
        else:
            raise  # TODO: be explicit

    async def exists_for_event(self, obj_in: CreateCallbackDto) -> bool:
        return await self._callback_repo.exists_by_platform_event_type_and_external_id(
            platform=obj_in.platform,
            event_type=obj_in.event_type,
            external_id=obj_in.external_id)

    async def soft_delete_callback(self, callback_id: str) -> bool:
        await self._callback_validator.should_exist_by_id(callback_id)
        await self._callback_repo.soft_delete(callback_id)

        return True

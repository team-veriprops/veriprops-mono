from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger

from main.appodus_utils import Page
from kink import inject, di

from main.appodus_utils.db.models import SuccessResponse
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.app.domain.user.auth.session.device.models import CreateDeviceDto, QueryDeviceDto, SearchDeviceDto, _UpdateDeviceDto, \
    _CreateDeviceDto
from main.app.domain.user.auth.session.device.repo import DeviceRepo
from main.app.domain.user.auth.session.device.validator import DeviceValidator
from main.appodus_utils.integrations.messaging.models import PushToken

logger: Logger = di['logger']


@inject
@decorate_all_methods(transactional())
@decorate_all_methods(method_trace_logger)
class DeviceService:
    def __init__(self, device_repo: DeviceRepo, device_validator: DeviceValidator):
        self._device_repo = device_repo
        self._device_validator = device_validator

    async def create_device(self, obj_in: CreateDeviceDto) -> SuccessResponse[QueryDeviceDto]:
        create_dto = _CreateDeviceDto.model_validate(obj_in.model_dump())
        return await self._device_repo.create(create_dto)

    async def get_device_page(self, search_dto: SearchDeviceDto) -> Page[QueryDeviceDto]:
        return await self._device_repo.get_page(search_dto=search_dto)

    async def update_device_push_token(self, device_id: str, push_token: PushToken) -> SuccessResponse[bool]:
        await self._device_validator.should_exist_by_id(device_id)

        obj_in = _UpdateDeviceDto(push_token=push_token)
        await self._device_repo.update(device_id, obj_in.model_dump(exclude_none=True))

        return SuccessResponse(
            data=True
        )

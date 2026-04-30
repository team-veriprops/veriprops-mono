from http import HTTPStatus
from typing import Dict, Any

from main.appodus_utils import Page
from fastapi import APIRouter, Depends
from kink import di

from main.appodus_utils.db.models import SuccessResponse
from main.app.domain.user.auth.session.device.models import CreateDeviceDto, QueryDeviceDto, SearchDeviceDto
from main.app.domain.user.auth.session.device.service import DeviceService
from main.appodus_utils.integrations.messaging.models import PushToken

device_service: DeviceService = di[DeviceService]
device_router = APIRouter(prefix="/devices", tags=["Devices"])


@device_router.post('/', response_model=SuccessResponse[QueryDeviceDto], status_code=HTTPStatus.CREATED)
async def create_device(create_dto: CreateDeviceDto) -> SuccessResponse[QueryDeviceDto]:
    return await device_service.create_device(create_dto)


@device_router.get('/', response_model=Page[QueryDeviceDto], status_code=HTTPStatus.OK)
async def get_device_page(search_dto: SearchDeviceDto = Depends()) -> Page[QueryDeviceDto]:
    return await device_service.get_device_page(search_dto)


@device_router.put('/{device_id}', response_model=SuccessResponse[bool], status_code=HTTPStatus.OK)
async def update_device_push_token(device_id: str, push_token: PushToken) -> SuccessResponse[bool]:
    return await device_service.update_device_push_token(device_id, push_token)

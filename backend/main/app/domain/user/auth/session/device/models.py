from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, JSON

from main.appodus_utils import BaseEntity, PageRequest, BaseQueryDto, Utils
from main.appodus_utils import Object
from main.appodus_utils.db.models import UTCDateTime
from main.appodus_utils.integrations.messaging.models import PushToken, PushProviderType


class Device(BaseEntity):
    __tablename__ = 'devices'
    user_id = Column(String(36), nullable=False)
    device_id = Column(String(36), nullable=False)
    push_provider_type = Column(String(20), nullable=False)
    push_token = Column(JSON, nullable=False)
    last_active = Column(UTCDateTime, nullable=False)


class DeviceBaseDto(Object):
    pass


class CreateDeviceDto(DeviceBaseDto):
    user_id: str
    device_id: str
    push_provider_type: PushProviderType
    push_token: PushToken


class _CreateDeviceDto(CreateDeviceDto):
    last_active: datetime = Utils.datetime_now()


class UpdateDeviceDto(DeviceBaseDto):
    pass


class _UpdateDeviceDto(DeviceBaseDto):
    push_token: Optional[PushToken] = None
    last_active: datetime = Utils.datetime_now()


class SearchDeviceDto(PageRequest, BaseQueryDto):
    user_id: Optional[str] = None
    push_provider_type: Optional[PushProviderType] = None


class QueryDeviceDto(_CreateDeviceDto, BaseQueryDto):
    pass

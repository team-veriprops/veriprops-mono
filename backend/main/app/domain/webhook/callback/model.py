import enum
from datetime import datetime
from typing import Optional, Any

from sqlalchemy import Column, String, Boolean, JSON, DateTime
from sqlalchemy.ext.mutable import MutableDict

from main.app.config.settings import IntegratedPlatform
from main.appodus_utils import BaseEntity, BaseQueryDto, PageRequest, Object


class CallbackType(str, enum.Enum):
    CONTRACT_UPDATED = 'CONTRACT_UPDATED'
    CONTRACT_SIGNED = 'CONTRACT_SIGNED'


class Callback(BaseEntity):
    __tablename__ = 'callbacks'
    platform = Column(String(20), nullable=False)
    event_type = Column(String(20), nullable=False)
    external_id = Column(String(97), nullable=False)
    payload = Column(MutableDict.as_mutable(JSON), nullable=False)
    handle_from_time = Column(DateTime(), nullable=False, default=False)
    handled = Column(Boolean, nullable=False, default=False)


class CallbackBaseDto(Object):
    pass


class CreateCallbackDto(CallbackBaseDto):
    platform: IntegratedPlatform
    event_type: CallbackType
    external_id: str
    payload: Any
    handle_from_time: datetime
    handled: bool = False


class UpdateCallbackDto(CallbackBaseDto):
    pass


class _UpdateCallbackDto(Object):
    handle_from_time: Optional[datetime] = None
    payload: Optional[Any] = None
    handled: Optional[bool] = None


class QueryCallbackDto(CreateCallbackDto, _UpdateCallbackDto, BaseQueryDto):
    pass


class SearchCallbackDto(PageRequest, BaseQueryDto):
    platform: Optional[IntegratedPlatform] = None
    event_type: Optional[CallbackType] = None
    external_id: Optional[str] = None
    payload: Optional[Any] = None
    handle_from_time: Optional[datetime] = None
    handled: Optional[bool] = None

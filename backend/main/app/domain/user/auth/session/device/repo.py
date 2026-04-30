from typing import Type

from kink import inject
from sqlalchemy import select, literal

from sqlalchemy.ext.asyncio import AsyncSession

from main.appodus_utils.db.repo import GenericRepo
from main.app.domain.user.auth.session.device.models import Device, CreateDeviceDto, UpdateDeviceDto, QueryDeviceDto, \
    SearchDeviceDto


@inject
class DeviceRepo(GenericRepo[Device, CreateDeviceDto, UpdateDeviceDto, QueryDeviceDto, SearchDeviceDto]):
    def __init__(self, db: AsyncSession, model: Type[Device] = Device, query_dto: Type[QueryDeviceDto] = QueryDeviceDto):
        super().__init__(db, model, query_dto)
        self.db = db
        
    async def get_by_device_id(self, device_id: str) -> QueryDeviceDto:
        stmt = select(self._model).where(
            self._model.deleted.is_(False),
            self._model.device_id == device_id
        )

        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()

        return self._db_utils.build_row_response(row)


    async def exists_by_device_id(self, device_id: str) -> bool:
        stmt = select(literal(True)).where(
            self._model.deleted.is_(False), self._model.device_id == device_id
        )
        result = await self._session.execute(stmt)
        return result.scalar() is not None

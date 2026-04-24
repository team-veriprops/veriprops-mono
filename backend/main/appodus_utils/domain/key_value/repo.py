from logging import Logger
from typing import Optional

from main.appodus_utils import Utils
from main.appodus_utils.db.session import get_db_session_from_context
from kink import inject, di
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.domain.key_value.models import UpsertKeyValue, KeyValue

logger: Logger =  di["logger"]
@inject
@decorate_all_methods(method_trace_logger)
class KeyValueRepo:

    @property
    def _session(self) -> AsyncSession:
        return get_db_session_from_context()

    async def get(self, key: str) -> Optional[UpsertKeyValue]:
        stmt = select(KeyValue).where(KeyValue.key == key)
        result = await self._session.execute(stmt)

        row: KeyValue = result.scalar_one_or_none()

        if not row:
            return None

        if row and row.is_expired:
            logger.info(f"Evicting from KeyValue Store: {row.value}")
            await self._session.delete(row)
            return None

        return UpsertKeyValue(key=row.key, value=row.value, expires_at=row.expires_at)

    async def upsert(self, obj_in: UpsertKeyValue):

        stmt = select(KeyValue).where(KeyValue.key == obj_in.key)
        result = await self._session.execute(stmt)
        db_obj = result.scalar_one_or_none()

        if db_obj:
            # Update only provided fields
            for field, value in obj_in.model_dump(exclude_unset=True).items():
                setattr(db_obj, field, value)
        else:
            db_obj = KeyValue(**obj_in.model_dump())
            self._session.add(db_obj)

        return db_obj

    async def delete(self, key: str):
        stmt = delete(KeyValue).where(KeyValue.key == key)
        await self._session.execute(stmt)
        await self._session.commit()

    async def cleanup_expired(self):
        stmt = delete(KeyValue).where(KeyValue.expires_at != None).where(KeyValue.expires_at <= Utils.datetime_now())
        await self._session.execute(stmt)
        await self._session.commit()

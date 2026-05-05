from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger
import datetime
import pickle
from datetime import timedelta
from typing import Any

from main.appodus_utils import Utils
from kink import inject, di

from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional, TransactionSessionPolicy
from main.appodus_utils.domain.key_value.models import UpsertKeyValue
from main.appodus_utils.domain.key_value.repo import KeyValueRepo

logger: Logger = di['logger']


@inject
@decorate_all_methods(transactional(session_policy=TransactionSessionPolicy.ALWAYS_NEW))
@decorate_all_methods(method_trace_logger)
class KeyValueService:
    def __init__(self, key_value_repo: KeyValueRepo):
        self._key_value_repo = key_value_repo

    async def set(self, key: str, time_to_live: timedelta, value: Any):
        value_bytes = pickle.dumps(value)
        time_to_live_sec = int(time_to_live.total_seconds())

        datetime_future = Utils.datetime_now() + datetime.timedelta(seconds=time_to_live_sec)

        data = UpsertKeyValue(key=key, value=value_bytes, expires_at=datetime_future)

        await self._key_value_repo.upsert(data)

    async def get(self, key: str) -> Any:
        data: UpsertKeyValue = await self._key_value_repo.get(key)
        if data:
            return pickle.loads(data.value)

        return None

    async def delete(self, key: str):
        await self._key_value_repo.delete(key)

    async def delete_by_prefix(self, prefix: str) -> int:
        return await self._key_value_repo.delete_by_prefix(prefix)

    async def cleanup_expired(self):
        await self._key_value_repo.cleanup_expired()

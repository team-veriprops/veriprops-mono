from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger
import datetime
from datetime import timedelta
from typing import Any, Optional

from main.appodus_utils import Utils
from kink import inject, di

from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional, TransactionSessionPolicy
from main.appodus_utils.domain.key_value.models import UpsertKeyValue
from main.appodus_utils.domain.key_value.repo import KeyValueRepo

logger: Logger = di['logger']


@inject
@decorate_all_methods(transactional(session_policy=TransactionSessionPolicy.INDEPENDENT))
@decorate_all_methods(method_trace_logger)
class KeyValueService:
    """Short-lived keyed state: OTP codes and counters, verified markers, the SQL fallback behind
    `RedisUtils`.

    INDEPENDENT: every write commits on its own, because the callers rely on it surviving their
    own failure (a wrong OTP guess is counted, then rejected with an error). The separate pool
    keeps those writes from waiting on the connection their caller holds.
    """
    def __init__(self, key_value_repo: KeyValueRepo):
        self._key_value_repo = key_value_repo

    async def set(self, key: str, time_to_live: timedelta, value: Any):
        # Store the UTF-8 text form (never pickle — deserializing pickle from the DB is a
        # latent RCE primitive). This is the SQL fallback behind RedisUtils, which returns
        # decoded strings, so values here are always simple string-serializable data.
        value_bytes = str(value).encode("utf-8")
        time_to_live_sec = int(time_to_live.total_seconds())

        datetime_future = Utils.datetime_now() + datetime.timedelta(seconds=time_to_live_sec)

        data = UpsertKeyValue(key=key, value=value_bytes, expires_at=datetime_future)

        await self._key_value_repo.upsert(data)

    async def get(self, key: str) -> Any:
        data: UpsertKeyValue = await self._key_value_repo.get(key)
        if data:
            # Mirror RedisUtils.get_redis's decoded-string return (Redis path does
            # result.decode("utf-8")), so both backends behave identically.
            return data.value.decode("utf-8")

        return None

    async def incr(
            self, key: str, time_to_live: timedelta, *, sliding: bool = False, limit: Optional[int] = None,
    ) -> Optional[int]:
        """Atomically count one hit at *key*; None when *limit* refused it (see `KeyValueRepo.incr`)."""
        return await self._key_value_repo.incr(key, time_to_live, sliding=sliding, limit=limit)

    async def pop(self, key: str) -> Optional[str]:
        """Consume *key*: its decoded value for exactly one caller, None for everyone else."""
        value = await self._key_value_repo.pop(key)
        return value.decode("utf-8") if value is not None else None

    async def delete(self, key: str):
        await self._key_value_repo.delete(key)

    async def delete_by_prefix(self, prefix: str) -> int:
        return await self._key_value_repo.delete_by_prefix(prefix)

    async def cleanup_expired(self):
        await self._key_value_repo.cleanup_expired()

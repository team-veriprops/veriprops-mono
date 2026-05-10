from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger
from datetime import timedelta
from typing import Any

from kink import di
from redis.asyncio import Redis

from main.appodus_utils.domain.key_value.service import KeyValueService

redis = di[Redis]
key_value_service: KeyValueService = di[KeyValueService]
logger: Logger = di['logger']

class RedisUtils:

    @staticmethod
    async def set_redis(key: str, value: Any, time_to_live: timedelta = None):
        try:
            if not time_to_live:
                time_to_live = timedelta(minutes=5)
            if redis:
                logger.debug("Connected to Redis Server to write")
                await redis.setex(key, time_to_live, value)
            else:
                await key_value_service.set(key, time_to_live, value)
        except Exception as exc:
            print(exc)

    @staticmethod
    async def get_redis(key: str) -> Any:
        try:
            if redis:
                logger.debug("Connected to Redis Server to read")
                return await redis.get(key).decode("utf-8")
            else:
                return await key_value_service.get(key)
        except Exception as exc:
            print(exc)

    @staticmethod
    async def delete(key: str) -> Any:
        try:
            if redis:
                logger.debug("Connected to Redis Server to delete")
                return await redis.delete(key)
            else:
                return await key_value_service.delete(key)
        except Exception as exc:
            print(exc)

    @staticmethod
    async def delete_by_prefix(prefix: str) -> int:
        """Delete all keys whose names start with *prefix*.

        Redis path: SCAN + batched DELETE (non-blocking, cursor-based).
        Fallback path (no Redis): delegates to KeyValueService which issues a
        SQL DELETE WHERE key LIKE '{prefix}%'.
        """
        try:
            if redis:
                count = 0
                cursor = 0
                while True:
                    cursor, keys = await redis.scan(cursor, match=f"{prefix}*", count=200)
                    if keys:
                        await redis.delete(*keys)
                        count += len(keys)
                    if cursor == 0:
                        break
                return count
            else:
                return await key_value_service.delete_by_prefix(prefix)
        except Exception as exc:
            print(exc)
            return 0

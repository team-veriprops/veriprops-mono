from datetime import timedelta
from logging import Logger
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

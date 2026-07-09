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
                result = await redis.get(key)
                return result.decode("utf-8") if result else None
            else:
                return await key_value_service.get(key)
        except Exception as exc:
            print(exc)

    @staticmethod
    async def incr_with_ttl(key: str, ttl_seconds: int) -> int:
        """Atomically increment a counter and (on first hit) set its TTL.

        Backs fixed-window rate limiting. Uses Redis INCR/EXPIRE when available; falls
        back to a best-effort read-modify-write via the SQL KV store (adequate for the
        low-per-IP-concurrency auth/OTP paths this guards). Fails OPEN (returns 0) on any
        backend error so a limiter outage never locks users out of authentication.
        """
        try:
            if redis:
                count = int(await redis.incr(key))
                if count == 1:
                    await redis.expire(key, ttl_seconds)
                return count
            current = await key_value_service.get(key)
            count = int(current or 0) + 1
            await key_value_service.set(key, timedelta(seconds=ttl_seconds), count)
            return count
        except Exception as exc:
            logger.warning(f"Rate-limit counter for {key!r} failed (allowing request): {exc}")
            return 0

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
    async def publish(channel: str, message: Any) -> None:
        """Publish a message to a Redis pub/sub channel (best-effort; no-op on failure)."""
        import json
        try:
            if redis:
                payload = json.dumps(message) if not isinstance(message, str) else message
                await redis.publish(channel, payload)
        except Exception as exc:
            logger.warning(f"Redis publish to {channel!r} failed: {exc}")

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

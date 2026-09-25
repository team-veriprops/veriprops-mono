from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger
from datetime import timedelta
from typing import Any, Optional

from kink import di
from redis.asyncio import Redis

from main.appodus_utils.domain.key_value.service import KeyValueService

redis = di[Redis]
key_value_service: KeyValueService = di[KeyValueService]
logger: Logger = di['logger']


class RedisUtils:
    """Key/value access over Redis when it is enabled, else the SQL key/value store.

    A backend failure is always logged with its traceback. By default the call then carries on
    (None, or 0 for counts), which suits caches and statistics. A caller whose correctness depends
    on the store passes `strict=True` and gets the exception instead: an unreadable token denylist
    must not read as "not revoked", and a revocation that was not written must not read as done.
    """

    @staticmethod
    async def set_redis(key: str, value: Any, time_to_live: timedelta = None, *, strict: bool = False):
        try:
            if not time_to_live:
                time_to_live = timedelta(minutes=5)
            if redis:
                logger.debug("Connected to Redis Server to write")
                await redis.setex(key, time_to_live, value)
            else:
                await key_value_service.set(key, time_to_live, value)
        except Exception:
            logger.exception("Key/value write of {!r} failed", key)
            if strict:
                raise

    @staticmethod
    async def get_redis(key: str, *, strict: bool = False) -> Any:
        try:
            if redis:
                logger.debug("Connected to Redis Server to read")
                result = await redis.get(key)
                return result.decode("utf-8") if result else None
            else:
                return await key_value_service.get(key)
        except Exception:
            logger.exception("Key/value read of {!r} failed", key)
            if strict:
                raise
            return None

    @staticmethod
    async def incr_with_ttl(key: str, ttl_seconds: int) -> int:
        """Atomically increment a fixed-window counter, starting its TTL on the first hit.

        Backs fixed-window rate limiting. Redis: INCR and EXPIRE NX in one transaction
        pipeline, so a counter can never be left without a TTL. SQL fallback: one atomic
        statement with the same fixed window. Fails OPEN (returns 0) on any backend error so
        a limiter outage never locks users out of authentication.
        """
        try:
            if redis:
                async with redis.pipeline(transaction=True) as pipe:
                    pipe.incr(key)
                    pipe.expire(key, ttl_seconds, nx=True)
                    count, _ = await pipe.execute()
                return int(count)
            return await key_value_service.incr(key, timedelta(seconds=ttl_seconds), sliding=False)
        except Exception:
            logger.exception("Rate-limit counter for {!r} failed (allowing request)", key)
            return 0

    @staticmethod
    async def pop(key: str, *, strict: bool = False) -> Optional[str]:
        """Read and delete *key* in one step (single-use tokens): exactly one caller gets it."""
        try:
            if redis:
                result = await redis.getdel(key)
                return result.decode("utf-8") if result else None
            return await key_value_service.pop(key)
        except Exception:
            logger.exception("Key/value pop of {!r} failed", key)
            if strict:
                raise
            return None

    @staticmethod
    async def delete(key: str, *, strict: bool = False) -> Any:
        try:
            if redis:
                logger.debug("Connected to Redis Server to delete")
                return await redis.delete(key)
            else:
                return await key_value_service.delete(key)
        except Exception:
            logger.exception("Key/value delete of {!r} failed", key)
            if strict:
                raise
            return None

    @staticmethod
    async def publish(channel: str, message: Any) -> None:
        """Publish a message to a Redis pub/sub channel (best-effort; no-op on failure)."""
        import json
        try:
            if redis:
                payload = json.dumps(message) if not isinstance(message, str) else message
                await redis.publish(channel, payload)
        except Exception:
            logger.exception("Redis publish to {!r} failed", channel)

    @staticmethod
    async def delete_by_prefix(prefix: str, *, strict: bool = False) -> int:
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
        except Exception:
            logger.exception("Key/value delete of prefix {!r} failed", prefix)
            if strict:
                raise
            return 0

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger
from datetime import timedelta
from typing import Optional

from main.appodus_utils import Utils
from main.appodus_utils.db.session import get_db_session_from_context
from kink import inject, di
from sqlalchemy import BigInteger, Text, case, cast, delete, func, literal, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.domain.key_value.models import UpsertKeyValue, KeyValue

logger: Logger = di["logger"]


@inject
@decorate_all_methods(method_trace_logger)
class KeyValueRepo:
    """The SQL key/value store behind `RedisUtils` and the OTP counters.

    Every operation is a single statement, so concurrent requests on one key can't interleave:
    no first-write race into the primary key, no lost counter increments, no read deleting a
    value that a concurrent write just refreshed. Values are UTF-8 text in a bytea column.
    """

    @property
    def _session(self) -> AsyncSession:
        return get_db_session_from_context()

    async def get(self, key: str) -> Optional[UpsertKeyValue]:
        now = Utils.datetime_now()
        result = await self._session.execute(
            select(KeyValue.value, KeyValue.expires_at).where(KeyValue.key == key)
        )
        row = result.first()
        if not row:
            return None

        if row.expires_at <= now:
            # Evict only if it is still expired: a concurrent set may have refreshed it.
            await self._session.execute(
                delete(KeyValue).where(KeyValue.key == key, KeyValue.expires_at <= now)
            )
            return None

        return UpsertKeyValue(key=key, value=row.value, expires_at=row.expires_at)

    async def upsert(self, obj_in: UpsertKeyValue) -> None:
        stmt = insert(KeyValue).values(key=obj_in.key, value=obj_in.value, expires_at=obj_in.expires_at)
        await self._session.execute(stmt.on_conflict_do_update(
            index_elements=[KeyValue.key],
            set_={"value": stmt.excluded.value, "expires_at": stmt.excluded.expires_at},
        ))

    async def incr(
            self, key: str, time_to_live: timedelta, *, sliding: bool = False, limit: Optional[int] = None,
    ) -> Optional[int]:
        """Add one to the counter at *key* and return the new count, in one statement.

        A missing or expired counter restarts at 1 with a fresh expiry. Otherwise the expiry
        stays where the window started (`sliding=False`, Redis INCR + EXPIRE NX parity) or
        moves to now + ttl on every hit (`sliding=True`). With *limit*, a live counter already
        at the limit is left untouched and None is returned, so a refused attempt neither counts
        nor extends the window.
        """
        now = Utils.datetime_now()
        fresh_expiry = now + time_to_live
        expired = KeyValue.expires_at <= now
        current = cast(func.convert_from(KeyValue.value, literal("UTF8")), BigInteger)

        stmt = insert(KeyValue).values(key=key, value=b"1", expires_at=fresh_expiry)
        stmt = stmt.on_conflict_do_update(
            index_elements=[KeyValue.key],
            set_={
                "value": case(
                    (expired, stmt.excluded.value),
                    else_=func.convert_to(cast(current + 1, Text), literal("UTF8")),
                ),
                "expires_at": (
                    stmt.excluded.expires_at if sliding
                    else case((expired, stmt.excluded.expires_at), else_=KeyValue.expires_at)
                ),
            },
            where=(expired | (current < limit)) if limit is not None else None,
        ).returning(KeyValue.value)

        value = (await self._session.execute(stmt)).scalar_one_or_none()
        return int(value.decode("utf-8")) if value is not None else None

    async def pop(self, key: str) -> Optional[bytes]:
        """Delete *key* and return its live value, or None. Exactly one caller gets a value."""
        now = Utils.datetime_now()
        result = await self._session.execute(
            delete(KeyValue).where(KeyValue.key == key).returning(KeyValue.value, KeyValue.expires_at)
        )
        row = result.first()
        if not row or row.expires_at <= now:
            return None
        return row.value

    async def delete(self, key: str) -> None:
        await self._session.execute(delete(KeyValue).where(KeyValue.key == key))

    async def delete_by_prefix(self, prefix: str) -> int:
        result = await self._session.execute(delete(KeyValue).where(KeyValue.key.like(f"{prefix}%")))
        return result.rowcount or 0

    async def cleanup_expired(self) -> None:
        await self._session.execute(delete(KeyValue).where(KeyValue.expires_at <= Utils.datetime_now()))

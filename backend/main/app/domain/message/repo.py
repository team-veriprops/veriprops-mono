import json
from datetime import datetime
from typing import List, Optional, Type

from kink import inject
from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.message.models import Message, SearchMessageDto, \
    QueryMessageDto, UpsertMessageDto
from main.appodus_utils import Utils
from main.appodus_utils.db.repo import GenericRepo
from main.appodus_utils.integrations.messaging.models import MessageStatus

# Timestamp columns that must be bound as datetimes, not the ISO strings a JSON-mode
# dump produces.
_DATETIME_COLUMNS = ("scheduled_at", "next_retry_at", "expires_at", "sent_at", "delivered_at")
# Statuses whose rows the drain sends once `next_retry_at` passes: queued deliveries and retries.
_DUE_STATUSES = (MessageStatus.PENDING.value, MessageStatus.RETRYING.value)


def message_row_to_dto(row: Message) -> QueryMessageDto:
    """A row as its DTO. Validated from a plain dict: the before-validator coerces the UUID
    primary key to its hex form only on dict input (from_attributes bypasses it, and the UUID
    then fails the str-typed id field)."""
    return QueryMessageDto.model_validate({column.key: getattr(row, column.key) for column in row.__table__.columns})


@inject
class MessageRepo(GenericRepo[Message, UpsertMessageDto, UpsertMessageDto, QueryMessageDto, SearchMessageDto]):
    def __init__(self, db: AsyncSession, model: Type[Message] = Message, query_dto: Type[QueryMessageDto] = QueryMessageDto):
        super().__init__(db, model, query_dto)
        self.db = db

    async def get_by_provider_id(self, provider_id: str) -> Optional[Message]:
        """The bookkeeping row for a send the provider knows by *provider_id* (a wamid)."""
        stmt = select(Message).where(
            and_(Message.deleted.is_(False), Message.provider_id == provider_id)
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_due(self, now: datetime, limit: int) -> List[QueryMessageDto]:
        """Rows whose turn to be sent has come, oldest turn first — the drain's batch.

        Two kinds: a queued delivery (PENDING, written by `MessagingService.enqueue_bulk`) and a
        retry (RETRYING). Both carry `next_retry_at`. An ordinary send still in flight is PENDING
        with no `next_retry_at`, and `NULL <= now` is never true, so the drain never touches it.
        """
        stmt = (
            select(Message)
            .where(
                Message.deleted.is_(False),
                Message.status.in_(_DUE_STATUSES),
                Message.next_retry_at <= now,
            )
            .order_by(Message.next_retry_at)
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [message_row_to_dto(row) for row in rows]

    async def lease_due(self, message_id: str, now: datetime, until: datetime) -> bool:
        """Take a due row for this run: push its `next_retry_at` to *until*, only while it is
        still queued or retrying, and due. Whether this run got it.

        Two overlapping drains (another worker, the admin endpoint) list the same due rows; only
        the one whose update lands sends. A run that dies mid-send leaves the row due again once
        *until* passes, so the message is not stranded.
        """
        stmt = (
            update(Message)
            .where(
                Message.id == self._ensure_uuid(message_id),
                Message.deleted.is_(False),
                Message.status.in_(_DUE_STATUSES),
                Message.next_retry_at <= now,
            )
            .values(next_retry_at=until)
            .returning(Message.id)
        )
        return (await self._session.execute(stmt)).scalar() is not None

    async def create_from_upsert(self, dto: UpsertMessageDto) -> Message:
        """Persist the bookkeeping row for a dispatch, keeping only real columns.

        ``UpsertMessageDto`` carries wire-only hints (e.g. ``sandbox_mode``) that the
        ``messages`` table has no column for — the stock create path would TypeError on
        them. A JSON-mode dump also keeps the nested to/payload JSONB values primitive.
        """
        data = json.loads(dto.model_dump_json(by_alias=False))
        columns = {c.key for c in Message.__table__.columns}
        data = {k: v for k, v in data.items() if k in columns}
        for field in _DATETIME_COLUMNS:
            if isinstance(data.get(field), str):
                data[field] = datetime.fromisoformat(data[field])

        row = Message(**data)
        row.id = self._ensure_uuid(row.id)
        row.version = 1
        row.date_created = Utils.datetime_now()
        self._session.add(row)
        # Flushed now: a send nested inside another independent transaction (a payout settled in
        # `PayoutDisbursementService._settle`) shares that session, and every later step checks
        # the row exists. With autoflush off, an unflushed row would be invisible to that check.
        await self._session.flush()
        return row

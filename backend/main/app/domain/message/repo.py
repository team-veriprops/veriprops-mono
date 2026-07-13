import json
from datetime import datetime
from typing import Type

from kink import inject
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.message.models import Message, SearchMessageDto, \
    QueryMessageDto, UpsertMessageDto
from main.appodus_utils import Utils
from main.appodus_utils.db.repo import GenericRepo

# Timestamp columns that must be bound as datetimes, not the ISO strings a JSON-mode
# dump produces.
_DATETIME_COLUMNS = ("scheduled_at", "next_retry_at", "expires_at", "sent_at", "delivered_at")


@inject
class MessageRepo(GenericRepo[Message, UpsertMessageDto, UpsertMessageDto, QueryMessageDto, SearchMessageDto]):
    def __init__(self, db: AsyncSession, model: Type[Message] = Message, query_dto: Type[QueryMessageDto] = QueryMessageDto):
        super().__init__(db, model, query_dto)
        self.db = db

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
        return row

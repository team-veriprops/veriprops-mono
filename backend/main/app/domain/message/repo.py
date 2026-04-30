from typing import Type

from kink import inject
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.message.models import Message, SearchMessageDto, \
    QueryMessageDto, UpsertMessageDto
from main.appodus_utils.db.repo import GenericRepo


@inject
class MessageRepo(GenericRepo[Message, UpsertMessageDto, UpsertMessageDto, QueryMessageDto, SearchMessageDto]):
    def __init__(self, db: AsyncSession, model: Type[Message] = Message, query_dto: Type[QueryMessageDto] = QueryMessageDto):
        super().__init__(db, model, query_dto)
        self.db = db

from typing import Type

from kink import inject
from sqlalchemy.ext.asyncio import AsyncSession

from main.appodus_utils.integrations.messaging.services.dead_letter_queue.models import DLQ, CreateDLQDto, UpdateDLQDto, SearchDLQDto, \
    QueryDLQDto
from main.appodus_utils.db.repo import GenericRepo


@inject
class DLQRepo(GenericRepo[DLQ, CreateDLQDto, UpdateDLQDto, QueryDLQDto, SearchDLQDto]):
    def __init__(self, db: AsyncSession, model: Type[DLQ] = DLQ, query_dto: Type[QueryDLQDto] = QueryDLQDto):
        super().__init__(db, model, query_dto)
        self.db = db

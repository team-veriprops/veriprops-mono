from typing import Type

from kink import inject
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.audit.models import (
    AuditLog,
    CreateAuditLogDto,
    QueryAuditLogDto,
    SearchAuditLogDto,
    UpdateAuditLogDto,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class AuditLogRepo(
    GenericRepo[
        AuditLog,
        CreateAuditLogDto,
        UpdateAuditLogDto,
        QueryAuditLogDto,
        SearchAuditLogDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[AuditLog] = AuditLog,
        query_dto: Type[QueryAuditLogDto] = QueryAuditLogDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

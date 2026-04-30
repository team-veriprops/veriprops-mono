from typing import List, Optional, Type

from kink import inject
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.user.auth.consent.models import (
    ConsentDocument,
    ConsentDocumentType,
    CreateConsentDocumentDto,
    CreateUserConsentDto,
    QueryConsentDocumentDto,
    QueryUserConsentDto,
    SearchConsentDocumentDto,
    SearchUserConsentDto,
    UpdateConsentDocumentDto,
    UpdateUserConsentDto,
    UserConsent,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class ConsentDocumentRepo(
    GenericRepo[
        ConsentDocument,
        CreateConsentDocumentDto,
        UpdateConsentDocumentDto,
        QueryConsentDocumentDto,
        SearchConsentDocumentDto,
    ]
):
    def __init__(
            self,
            db: AsyncSession,
            model: Type[ConsentDocument] = ConsentDocument,
            query_dto: Type[QueryConsentDocumentDto] = QueryConsentDocumentDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def get_current(self, doc_type: ConsentDocumentType) -> Optional[ConsentDocument]:
        stmt = (
            select(ConsentDocument)
            .where(
                ConsentDocument.deleted.is_(False),
                ConsentDocument.type == doc_type.value,
            )
            .order_by(desc(ConsentDocument.effective_at))
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_current_for_types(
            self, doc_types: List[ConsentDocumentType]
    ) -> List[ConsentDocument]:
        rows: List[ConsentDocument] = []
        for t in doc_types:
            row = await self.get_current(t)
            if row:
                rows.append(row)
        return rows


@inject
class UserConsentRepo(
    GenericRepo[
        UserConsent,
        CreateUserConsentDto,
        UpdateUserConsentDto,
        QueryUserConsentDto,
        SearchUserConsentDto,
    ]
):
    def __init__(
            self,
            db: AsyncSession,
            model: Type[UserConsent] = UserConsent,
            query_dto: Type[QueryUserConsentDto] = QueryUserConsentDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def latest_for_user(self, user_id: str, doc_type: ConsentDocumentType) -> Optional[UserConsent]:
        stmt = (
            select(UserConsent)
            .where(
                UserConsent.deleted.is_(False),
                UserConsent.user_id == user_id,
                UserConsent.document_type == doc_type.value,
            )
            .order_by(desc(UserConsent.accepted_at))
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

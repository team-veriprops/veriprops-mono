from typing import List, Optional, Type

from kink import inject
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.user.agent.models import (
    AgentApplicationDraft,
    AgentCoverage,
    AgentCredential,
    AgentProfile,
    CreateAgentApplicationDraftDto,
    CreateAgentCoverageDto,
    CreateAgentCredentialDto,
    CreateAgentProfileDto,
    CreateKycRecordDto,
    KycRecord,
    QueryAgentApplicationDraftDto,
    QueryAgentCoverageDto,
    QueryAgentCredentialDto,
    QueryAgentProfileDto,
    QueryKycRecordDto,
    SearchAgentApplicationDraftDto,
    SearchAgentCoverageDto,
    SearchAgentCredentialDto,
    SearchAgentProfileDto,
    SearchKycRecordDto,
    UpdateAgentApplicationDraftDto,
    UpdateAgentCoverageDto,
    UpdateAgentCredentialDto,
    UpdateAgentProfileDto,
    UpdateKycRecordDto,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class AgentProfileRepo(
    GenericRepo[
        AgentProfile,
        CreateAgentProfileDto,
        UpdateAgentProfileDto,
        QueryAgentProfileDto,
        SearchAgentProfileDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[AgentProfile] = AgentProfile,
        query_dto: Type[QueryAgentProfileDto] = QueryAgentProfileDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def get_by_user_id(self, user_id: str) -> Optional[AgentProfile]:
        stmt = select(AgentProfile).where(
            AgentProfile.deleted.is_(False),
            AgentProfile.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def page_applications(
        self, status: Optional[str], offset: int, limit: int
    ) -> tuple[List[AgentProfile], int]:
        from sqlalchemy import func

        conditions = [AgentProfile.deleted.is_(False)]
        if status:
            conditions.append(AgentProfile.status == status)
        base = select(AgentProfile).where(*conditions)
        total = await self._session.scalar(select(func.count()).select_from(base.subquery()))
        rows = (
            await self._session.execute(
                base.order_by(desc(AgentProfile.submitted_at)).offset(offset).limit(limit)
            )
        ).scalars().all()
        return list(rows), total or 0


@inject
class AgentCredentialRepo(
    GenericRepo[
        AgentCredential,
        CreateAgentCredentialDto,
        UpdateAgentCredentialDto,
        QueryAgentCredentialDto,
        SearchAgentCredentialDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[AgentCredential] = AgentCredential,
        query_dto: Type[QueryAgentCredentialDto] = QueryAgentCredentialDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def list_for_user(self, user_id: str) -> List[AgentCredential]:
        stmt = select(AgentCredential).where(
            AgentCredential.deleted.is_(False),
            AgentCredential.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


@inject
class AgentCoverageRepo(
    GenericRepo[
        AgentCoverage,
        CreateAgentCoverageDto,
        UpdateAgentCoverageDto,
        QueryAgentCoverageDto,
        SearchAgentCoverageDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[AgentCoverage] = AgentCoverage,
        query_dto: Type[QueryAgentCoverageDto] = QueryAgentCoverageDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def list_for_user(self, user_id: str) -> List[AgentCoverage]:
        stmt = select(AgentCoverage).where(
            AgentCoverage.deleted.is_(False),
            AgentCoverage.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


@inject
class AgentApplicationDraftRepo(
    GenericRepo[
        AgentApplicationDraft,
        CreateAgentApplicationDraftDto,
        UpdateAgentApplicationDraftDto,
        QueryAgentApplicationDraftDto,
        SearchAgentApplicationDraftDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[AgentApplicationDraft] = AgentApplicationDraft,
        query_dto: Type[QueryAgentApplicationDraftDto] = QueryAgentApplicationDraftDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def get_active_for_user(self, user_id: str) -> Optional[AgentApplicationDraft]:
        stmt = (
            select(AgentApplicationDraft)
            .where(
                AgentApplicationDraft.deleted.is_(False),
                AgentApplicationDraft.user_id == user_id,
            )
            .order_by(desc(AgentApplicationDraft.date_created))
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()


@inject
class KycRecordRepo(
    GenericRepo[
        KycRecord,
        CreateKycRecordDto,
        UpdateKycRecordDto,
        QueryKycRecordDto,
        SearchKycRecordDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[KycRecord] = KycRecord,
        query_dto: Type[QueryKycRecordDto] = QueryKycRecordDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def get_latest_for_user(self, user_id: str) -> Optional[KycRecord]:
        stmt = (
            select(KycRecord)
            .where(
                KycRecord.deleted.is_(False),
                KycRecord.user_id == user_id,
            )
            .order_by(desc(KycRecord.date_created))
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

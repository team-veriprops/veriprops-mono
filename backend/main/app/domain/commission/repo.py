"""Commission repos — S47."""
from __future__ import annotations

from decimal import Decimal
from typing import List, Optional, Type

from sqlalchemy import select
from kink import inject
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.commission.models import (
    CommissionRule,
    Earning,
    CreateCommissionRuleDto,
    UpdateCommissionRuleDto,
    QueryCommissionRuleDto,
    SearchCommissionRuleDto,
    CreateEarningDto,
    UpdateEarningDto,
    QueryEarningDto,
    SearchEarningDto,
    EarningStatus,
)
from main.appodus_utils.db.repo import GenericRepo
from main.appodus_utils.db.session import get_db_session_from_context


@inject
class CommissionRuleRepo(GenericRepo[
    CommissionRule,
    CreateCommissionRuleDto,
    UpdateCommissionRuleDto,
    QueryCommissionRuleDto,
    SearchCommissionRuleDto,
]):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[CommissionRule] = CommissionRule,
        query_dto: Type[QueryCommissionRuleDto] = QueryCommissionRuleDto,
    ):
        super().__init__(db, model, query_dto)

    async def get_for_role_and_tier(self, role: str, tier: str) -> Optional[CommissionRule]:
        session = get_db_session_from_context()
        result = await session.execute(
            select(CommissionRule).where(
                CommissionRule.role == role,
                CommissionRule.tier == tier,
                CommissionRule.deleted == False,
            ).order_by(CommissionRule.effective_date.desc()).limit(1)
        )
        return result.scalars().first()


@inject
class EarningRepo(GenericRepo[
    Earning,
    CreateEarningDto,
    UpdateEarningDto,
    QueryEarningDto,
    SearchEarningDto,
]):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[Earning] = Earning,
        query_dto: Type[QueryEarningDto] = QueryEarningDto,
    ):
        super().__init__(db, model, query_dto)

    async def list_for_agent(self, agent_id: str) -> List[Earning]:
        session = get_db_session_from_context()
        result = await session.execute(
            select(Earning).where(
                Earning.agent_id == agent_id,
                Earning.deleted == False,
            ).order_by(Earning.date_created.desc())
        )
        return list(result.scalars().all())

    async def sum_available(self, agent_id: str) -> Decimal:
        from sqlalchemy import func
        session = get_db_session_from_context()
        result = await session.execute(
            select(func.sum(Earning.net_amount)).where(
                Earning.agent_id == agent_id,
                Earning.status == EarningStatus.PENDING.value,
                Earning.deleted == False,
            )
        )
        return result.scalar() or Decimal("0")

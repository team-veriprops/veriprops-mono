"""Commission Rules data access."""
from __future__ import annotations

from typing import List, Optional, Type

from kink import inject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.commission_rule.models import (
    CommissionRule,
    CreateCommissionRuleDto,
    QueryCommissionRuleDto,
    SearchCommissionRuleDto,
    UpdateCommissionRuleDto,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class CommissionRuleRepo(
    GenericRepo[
        CommissionRule,
        CreateCommissionRuleDto,
        UpdateCommissionRuleDto,
        QueryCommissionRuleDto,
        SearchCommissionRuleDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[CommissionRule] = CommissionRule,
        query_dto: Type[QueryCommissionRuleDto] = QueryCommissionRuleDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def list_all(self) -> List[CommissionRule]:
        stmt = select(CommissionRule).where(CommissionRule.deleted.is_(False))
        return list((await self._session.execute(stmt)).scalars().all())

    async def get_for_role_tier(self, role: str, tier: str) -> Optional[CommissionRule]:
        stmt = select(CommissionRule).where(
            CommissionRule.deleted.is_(False),
            CommissionRule.role == role,
            CommissionRule.tier == tier,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

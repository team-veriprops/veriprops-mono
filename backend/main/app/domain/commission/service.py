"""Commission service — S47."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional, TYPE_CHECKING

from kink import di, inject

from main.app.domain.commission.models import (
    CommissionPreviewDto,
    CommissionRuleDto,
    CreateCommissionRuleDto,
    CreateEarningDto,
    EarningDto,
    EarningStatus,
    EarningsSummaryDto,
    SearchEarningDto,
    UpdateCommissionRuleDto,
)
from main.app.domain.commission.repo import CommissionRuleRepo, EarningRepo
from main.appodus_utils import Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import ResourceNotFoundException

if TYPE_CHECKING:
    from loguru import Logger

logger: "Logger" = di["logger"]


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class CommissionService:
    def __init__(self, rule_repo: CommissionRuleRepo, earning_repo: EarningRepo):
        self._rule_repo = rule_repo
        self._earning_repo = earning_repo

    async def get_rate(self, role: str, tier: str) -> Optional[float]:
        rule = await self._rule_repo.get_for_role_and_tier(role, tier)
        return float(rule.percentage) if rule else None

    async def compute_and_record(
        self,
        task_id: str,
        agent_id: str,
        verification_id: str,
        role: str,
        tier: str,
        gross_amount: float,
    ) -> EarningDto:
        rate = await self.get_rate(role, tier) or 0.0
        net_amount = round(gross_amount * rate / 100, 2)
        now_str = str(Utils.datetime_now())
        row = await self._earning_repo.create(CreateEarningDto(
            agent_id=agent_id,
            task_id=task_id,
            verification_id=verification_id,
            gross_amount=gross_amount,
            commission_pct=rate,
            net_amount=net_amount,
            status=EarningStatus.PENDING.value,
            computed_at=now_str,
        ))
        return self._earning_to_dto(row)

    async def get_earnings_summary(self, agent_id: str) -> EarningsSummaryDto:
        rows = await self._earning_repo.list_for_agent(agent_id)
        total = sum(float(r.net_amount) for r in rows)
        paid = sum(float(r.net_amount) for r in rows if r.status == EarningStatus.PAID.value)
        on_hold = sum(float(r.net_amount) for r in rows if r.status == EarningStatus.ON_HOLD.value)
        pending = sum(float(r.net_amount) for r in rows if r.status == EarningStatus.PENDING.value)
        return EarningsSummaryDto(
            total_lifetime=total,
            total_pending=pending,
            total_available=pending,
            total_paid=paid,
        )

    async def list_earnings(self, agent_id: str) -> List[EarningDto]:
        rows = await self._earning_repo.list_for_agent(agent_id)
        return [self._earning_to_dto(r) for r in rows]

    async def available_balance(self, agent_id: str) -> Decimal:
        return await self._earning_repo.sum_available(agent_id)

    async def get_commission_preview(self, role: str, tier: str, gross_amount: float) -> CommissionPreviewDto:
        rate = await self.get_rate(role, tier) or 0.0
        return CommissionPreviewDto(
            role=role,
            tier=tier,
            percentage=rate,
            estimated_net=round(gross_amount * rate / 100, 2),
        )

    # ── Admin rule management ─────────────────────────────────────

    async def list_rules(self) -> List[CommissionRuleDto]:
        from main.app.domain.commission.models import SearchCommissionRuleDto
        rows = await self._rule_repo.get_all(SearchCommissionRuleDto())
        return [self._rule_to_dto(r) for r in rows]

    async def create_rule(self, dto: CreateCommissionRuleDto) -> CommissionRuleDto:
        row = await self._rule_repo.create(dto)
        return self._rule_to_dto(row)

    async def update_rule(self, rule_id: str, dto: UpdateCommissionRuleDto) -> CommissionRuleDto:
        await self._rule_repo.update(rule_id, dto)
        row = await self._rule_repo.get_model(rule_id)
        if row is None:
            raise ResourceNotFoundException(resource="CommissionRule")
        return self._rule_to_dto(row)

    def _earning_to_dto(self, row) -> EarningDto:
        return EarningDto(
            id=str(row.id),
            agent_id=str(row.agent_id),
            task_id=str(row.task_id),
            verification_id=str(row.verification_id),
            gross_amount=float(row.gross_amount),
            commission_pct=float(row.commission_pct),
            net_amount=float(row.net_amount),
            status=EarningStatus(row.status),
            computed_at=str(row.computed_at),
            date_created=str(row.date_created),
        )

    def _rule_to_dto(self, row) -> CommissionRuleDto:
        return CommissionRuleDto(
            id=str(row.id),
            role=row.role,
            tier=row.tier,
            percentage=float(row.percentage),
            effective_date=str(row.effective_date),
            date_created=str(row.date_created),
        )

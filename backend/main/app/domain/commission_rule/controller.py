"""Commission Rules admin controller (PRD §20.1 / D97).

URL shape: /admin/commission-rules — RBAC-gated (CONFIGURE_PRICING, the Finance role). One fixed
commission per agent role, the same on every tier.
Frontend service: frontend/src/components/admin/finance/libs/commission-rule-service.
"""
from __future__ import annotations

from typing import Dict, List

from fastapi import APIRouter, Depends
from kink import di

from main.app.core.state.status import AgentRole
from main.app.domain.commission_rule.models import CommissionRule, CommissionRuleDto, SetCommissionRuleDto
from main.app.domain.commission_rule.service import CommissionRuleService
from main.app.domain.user.auth.utils.permissions import Permission, require_permission
from main.appodus_utils.db.models import SuccessResponse

commission_rule_router = APIRouter(prefix="/admin/commission-rules", tags=["Admin: Commission Rules"])
rule_service: CommissionRuleService = di[CommissionRuleService]


def _rule_dto(r: CommissionRule) -> CommissionRuleDto:
    return CommissionRuleDto(
        id=r.id, role=AgentRole(r.role),
        amount_ngn_kobo=r.amount_ngn_kobo, date_created=r.date_created,
    )


@commission_rule_router.get("", response_model=SuccessResponse[List[CommissionRuleDto]])
async def list_rules(_admin_id: str = Depends(require_permission(Permission.CONFIGURE_PRICING))):
    """Every configured role's fixed commission, in ``AgentRole`` order (§20.1)."""
    by_role: Dict[str, CommissionRule] = {r.role: r for r in await rule_service.list_all()}
    ordered = [_rule_dto(by_role[role.value]) for role in AgentRole if role.value in by_role]
    return SuccessResponse[List[CommissionRuleDto]](data=ordered)


@commission_rule_router.put("/{role}", response_model=SuccessResponse[CommissionRuleDto])
async def set_rule(
    role: AgentRole,
    req: SetCommissionRuleDto,
    admin_id: str = Depends(require_permission(Permission.CONFIGURE_PRICING)),
):
    rule = await rule_service.set_rule(role, req.amount_ngn_kobo, admin_id)
    return SuccessResponse[CommissionRuleDto](data=_rule_dto(rule))

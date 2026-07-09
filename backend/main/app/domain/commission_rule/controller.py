"""Commission Rules admin controller (PRD §15.1 / D30).

URL shape: /admin/commission-rules — RBAC-gated (CONFIGURE_PRICING, the Finance role).
Frontend service: frontend/src/components/admin/finance/libs/commission-rule-service.
"""
from __future__ import annotations

from typing import Dict, List

from fastapi import APIRouter, Depends
from kink import di

from main.app.core.state.dependencies import roles_for_tier
from main.app.core.state.status import AgentRole, VerificationTier
from main.app.domain.commission_rule.models import CommissionRule, CommissionRuleDto, SetCommissionRuleDto
from main.app.domain.commission_rule.service import CommissionRuleService
from main.app.domain.user.auth.utils.permissions import Permission, require_permission
from main.appodus_utils.db.models import SuccessResponse

commission_rule_router = APIRouter(prefix="/admin/commission-rules", tags=["Admin: Commission Rules"])
rule_service: CommissionRuleService = di[CommissionRuleService]


def _rule_dto(r: CommissionRule) -> CommissionRuleDto:
    return CommissionRuleDto(
        id=r.id, role=AgentRole(r.role), tier=VerificationTier(r.tier),
        rate_bps=r.rate_bps, date_created=r.date_created,
    )


@commission_rule_router.get("", response_model=SuccessResponse[List[CommissionRuleDto]])
async def list_rules(_admin_id: str = Depends(require_permission(Permission.CONFIGURE_PRICING))):
    """All configured rates, ordered by tier then the tier's role order (§15.1)."""
    rules = await rule_service.list_all()
    by_key: Dict[tuple, CommissionRule] = {(r.tier, r.role): r for r in rules}
    ordered: List[CommissionRuleDto] = []
    for tier in VerificationTier:
        for role in roles_for_tier(tier):
            rule = by_key.get((tier.value, role.value))
            if rule is not None:
                ordered.append(_rule_dto(rule))
    return SuccessResponse[List[CommissionRuleDto]](data=ordered)


@commission_rule_router.put("/{tier}/{role}", response_model=SuccessResponse[CommissionRuleDto])
async def set_rule(
    tier: VerificationTier,
    role: AgentRole,
    req: SetCommissionRuleDto,
    admin_id: str = Depends(require_permission(Permission.CONFIGURE_PRICING)),
):
    rule = await rule_service.set_rule(role, tier, req.rate_bps, admin_id)
    return SuccessResponse[CommissionRuleDto](data=_rule_dto(rule))

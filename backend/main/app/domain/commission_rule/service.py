"""Commission Rules service (PRD §15.1 / D30).

Owns the admin per-role×tier commission rates and the single kobo-exact commission
computation used at accrual and on the job-accept preview. Default rates are seeded by
migration 0001 (from ``DEFAULT_TRUST_WEIGHTS``) to reproduce the prior flat model
(``weight_percent/100 × AGENT_COMMISSION_SHARE``), so adopting the table changes no
accrued amount.
"""
from __future__ import annotations

from typing import List

from kink import inject

from main.app.core.state.status import AgentRole, VerificationTier
from main.app.domain.audit.models import AuditActionType
from main.app.domain.audit.service import AuditLogService
from main.app.domain.commission_rule.models import (
    CommissionRule,
    CreateCommissionRuleDto,
    UpdateCommissionRuleDto,
    FULL_BPS,
)
from main.app.domain.commission_rule.repo import CommissionRuleRepo
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import ValidationException

@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class CommissionRuleService:
    def __init__(
        self,
        rule_repo: CommissionRuleRepo,
        audit_service: AuditLogService,
    ):
        self._rule_repo = rule_repo
        self._audit = audit_service

    async def list_all(self) -> List[CommissionRule]:
        return await self._rule_repo.list_all()

    async def get_agent_share_bps(self, role: AgentRole, tier: VerificationTier) -> int:
        """The configured rate (basis points) for a role × tier — 0 if unconfigured."""
        rule = await self._rule_repo.get_for_role_tier(role.value, tier.value)
        return rule.rate_bps if rule is not None else 0

    async def commission_minor(
        self, price_locked_minor: int, role: AgentRole, tier: VerificationTier
    ) -> int:
        """Kobo-exact agent commission for one task = price × rate_bps / 10_000."""
        rate_bps = await self.get_agent_share_bps(role, tier)
        return (price_locked_minor * rate_bps) // FULL_BPS

    async def set_rule(
        self, role: AgentRole, tier: VerificationTier, rate_bps: int, admin_id: str
    ) -> CommissionRule:
        """Upsert a single (role × tier) rate (§15.1). Audited."""
        if not 0 <= rate_bps <= FULL_BPS:
            raise ValidationException(
                message=f"Rate must be between 0 and {FULL_BPS} basis points."
            )
        existing = await self._rule_repo.get_for_role_tier(role.value, tier.value)
        if existing is None:
            row = await self._rule_repo.create_return_model(CreateCommissionRuleDto(
                role=role, tier=tier, rate_bps=rate_bps,
            ))
        else:
            await self._rule_repo.update(existing.id, UpdateCommissionRuleDto(rate_bps=rate_bps))
            row = await self._rule_repo.get_model(existing.id)
        self._audit.schedule(
            action=AuditActionType.ADMIN_CONFIG_CHANGED,
            resource_type="commission_rule", resource_id=row.id, actor_id=admin_id,
            details={"role": role.value, "tier": tier.value, "rate_bps": rate_bps},
        )
        return row

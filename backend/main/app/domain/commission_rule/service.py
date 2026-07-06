"""Commission Rules service (PRD §15.1 / D30).

Owns the admin per-role×tier commission rates and the single kobo-exact commission
computation used at accrual and on the job-accept preview. Default rates are seeded
idempotently to reproduce the prior flat model (``weight_percent/100 ×
AGENT_COMMISSION_SHARE``), so adopting the table changes no accrued amount.
"""
from __future__ import annotations

from typing import List

from kink import inject

from main.app.config.settings import settings
from main.app.core.state.dependencies import roles_for_tier
from main.app.core.state.status import AgentRole, VerificationTier
from main.app.domain.audit.models import AuditActionType
from main.app.domain.audit.service import AuditLogService
from main.app.domain.commission_rule.models import (
    BPS_PER_PERCENT,
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

# Default role weight share per tier (percent of the tier price allocated across roles), mirroring
# the Trust-Score-Weights defaults. Held statically here so seeding is deterministic and never
# depends on the trust-weight rows being visible mid-seed-transaction. The seeded commission rate
# is ``weight_percent/100 × AGENT_COMMISSION_SHARE`` (D30 — reproduces the prior flat model).
_DEFAULT_ROLE_WEIGHTS: dict[VerificationTier, dict[AgentRole, int]] = {
    VerificationTier.BASIC: {AgentRole.REGISTRY: 100},
    VerificationTier.STANDARD: {AgentRole.REGISTRY: 40, AgentRole.FIELD: 30, AgentRole.SURVEYOR: 30},
    VerificationTier.PREMIUM: {
        AgentRole.REGISTRY: 30, AgentRole.FIELD: 20, AgentRole.SURVEYOR: 20, AgentRole.LAWYER: 30,
    },
}


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class CommissionRuleService:
    def __init__(
        self,
        rule_repo: CommissionRuleRepo,
        audit_service: AuditLogService,
    ):
        self._repo = rule_repo
        self._audit = audit_service

    async def seed_defaults(self) -> None:
        """Idempotently ensure a rate exists for every (role, tier) in the tier's role set,
        computed to reproduce the prior flat model (``weight/100 × AGENT_COMMISSION_SHARE``)."""
        for tier in VerificationTier:
            weights = _DEFAULT_ROLE_WEIGHTS.get(tier, {})
            for role in roles_for_tier(tier):
                if await self._repo.get_for_role_tier(role.value, tier.value) is not None:
                    continue
                rate_bps = self._default_rate_bps(weights.get(role, 0))
                await self._repo.create_return_model(CreateCommissionRuleDto(
                    role=role, tier=tier, rate_bps=rate_bps,
                ))

    async def list_all(self) -> List[CommissionRule]:
        return await self._repo.list_all()

    async def get_agent_share_bps(self, role: AgentRole, tier: VerificationTier) -> int:
        """The configured rate (basis points) for a role × tier — 0 if unconfigured."""
        rule = await self._repo.get_for_role_tier(role.value, tier.value)
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
        existing = await self._repo.get_for_role_tier(role.value, tier.value)
        if existing is None:
            row = await self._repo.create_return_model(CreateCommissionRuleDto(
                role=role, tier=tier, rate_bps=rate_bps,
            ))
        else:
            await self._repo.update(existing.id, UpdateCommissionRuleDto(rate_bps=rate_bps))
            row = await self._repo.get_model(existing.id)
        self._audit.schedule(
            action=AuditActionType.ADMIN_CONFIG_CHANGED,
            resource_type="commission_rule", resource_id=row.id, actor_id=admin_id,
            details={"role": role.value, "tier": tier.value, "rate_bps": rate_bps},
        )
        return row

    # ── helpers ───────────────────────────────────────────────────

    @staticmethod
    def _default_rate_bps(weight_percent: int) -> int:
        """weight_percent/100 × AGENT_COMMISSION_SHARE, expressed in basis points."""
        return round(weight_percent * BPS_PER_PERCENT * settings.AGENT_COMMISSION_SHARE)

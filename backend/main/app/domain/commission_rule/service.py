"""Commission Rules service (PRD §20.1 / D97).

Owns the admin-set fixed commission per agent role and is the single place that answers
"what does this task pay?" — at accrual (report release) and on the agent's task card before
they accept. The answer depends on the role alone: never the tier, never the price, so no job
pays more for the same work. Defaults are seeded by migration ``0002_fixed_agent_commission``
from ``DEFAULT_ROLE_COMMISSION_NGN_KOBO``.
"""
from __future__ import annotations

from typing import Dict, List

from kink import inject

from main.app.core.state.status import AgentRole
from main.app.domain.audit.models import AuditActionType
from main.app.domain.audit.service import AuditLogService
from main.app.domain.commission_rule.margin import CommissionMarginGuard
from main.app.domain.commission_rule.models import CommissionRule, CreateCommissionRuleDto
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
        commission_margin_guard: CommissionMarginGuard,
    ):
        self._rule_repo = rule_repo
        self._audit = audit_service
        self._margin_guard = commission_margin_guard

    async def list_all(self) -> List[CommissionRule]:
        return await self._rule_repo.list_all()

    async def commission_minor(self, role: AgentRole) -> int:
        """The fixed commission (NGN kobo) one approved task of *role* pays — 0 if unconfigured."""
        rule = await self._rule_repo.get_for_role(role.value)
        return int(rule.amount_ngn_kobo) if rule is not None else 0

    async def commission_by_role(self) -> Dict[AgentRole, int]:
        """Every role's fixed commission in one read (0 where unconfigured) — for lists that
        show a figure per task without a lookup per row."""
        configured = {r.role: int(r.amount_ngn_kobo) for r in await self._rule_repo.list_all()}
        return {role: configured.get(role.value, 0) for role in AgentRole}

    async def set_rule(self, role: AgentRole, amount_ngn_kobo: int, admin_id: str) -> CommissionRule:
        """Upsert one role's fixed commission (§20.1). Refused when it would leave any tier
        needing this role below the minimum margin. Audited."""
        if amount_ngn_kobo < 0:
            raise ValidationException(message="The commission cannot be negative.")
        await self._margin_guard.check(commission_overrides={role: amount_ngn_kobo})
        row = await self._rule_repo.upsert(
            CreateCommissionRuleDto(role=role, amount_ngn_kobo=amount_ngn_kobo).model_dump(by_alias=False),
            ["amount_ngn_kobo"],
            unique_index="uq_commission_rule_role",
        )
        self._audit.schedule(
            action=AuditActionType.ADMIN_CONFIG_CHANGED,
            resource_type="commission_rule", resource_id=row.id, actor_id=admin_id,
            details={"role": role.value, "amount_ngn_kobo": amount_ngn_kobo},
        )
        return row

"""Commission Rules domain (PRD §20.1 / D97).

An agent's commission is a **fixed amount per role**: every approved REGISTRY task pays the same,
whatever tier the case was bought at and whatever the customer actually paid. A share of the tier
price would pay the same work more on a higher tier — and less on a referral-discounted case —
which steers agents towards the expensive jobs; a flat per-role figure removes that incentive by
construction, since the table has no tier to vary by.

The amount is admin-configured (RBAC ``CONFIGURE_PRICING``), shown on the agent's task card before
they accept (§12.1), and accrued as a CLEARING commission at report release (§20.2). It is held in
NGN kobo, the currency agents are paid out in.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Column, String

from main.appodus_utils.db.models import live_unique_index

from main.app.core.state.status import AgentRole
from main.appodus_utils import BaseEntity, BaseQueryDto, Object, InternalPageRequest

# The seeded fixed commission per role, in NGN kobo (₦1 = 100 kobo). Migration
# ``0002_fixed_agent_commission`` seeds these; admins edit them afterwards.
DEFAULT_ROLE_COMMISSION_NGN_KOBO: dict[AgentRole, int] = {
    AgentRole.REGISTRY: 2_000_000,   # ₦20,000
    AgentRole.FIELD: 1_440_000,      # ₦14,400
    AgentRole.SURVEYOR: 1_440_000,   # ₦14,400
    AgentRole.LAWYER: 3_600_000,     # ₦36,000
}


# ─── ORM ──────────────────────────────────────────────────────────

class CommissionRule(BaseEntity):
    __tablename__ = "commission_rules"

    role = Column(String(16), nullable=False)
    # Fixed commission paid for one approved task of this role, in NGN kobo.
    amount_ngn_kobo = Column(BigInteger, nullable=False, default=0)

    __table_args__ = (
        live_unique_index("uq_commission_rule_role", "role"),
    )


# ─── DTOs ─────────────────────────────────────────────────────────

class CreateCommissionRuleDto(Object):
    role: AgentRole
    amount_ngn_kobo: int


class UpdateCommissionRuleDto(Object):
    amount_ngn_kobo: Optional[int] = None


class QueryCommissionRuleDto(BaseQueryDto):
    role: Optional[str] = None


class SearchCommissionRuleDto(InternalPageRequest, BaseQueryDto):
    role: Optional[str] = None


class CommissionRuleDto(Object):
    id: str
    role: AgentRole
    amount_ngn_kobo: int
    date_created: datetime


class SetCommissionRuleDto(Object):
    """Admin sets one role's fixed commission, in NGN kobo."""

    amount_ngn_kobo: int

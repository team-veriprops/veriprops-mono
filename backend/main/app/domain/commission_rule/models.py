"""Commission Rules domain (PRD §15.1 / D30).

The agent commission is admin-configured **per role × tier**, shown on the job-accept
screen before an agent commits (§15.1) and used at report release to accrue the CLEARING
commission (§15.2). The rate is stored in **basis points** (1% = 100 bps) so the kobo math
is exact: ``commission = price_locked_minor × rate_bps / 10_000``.

Default rates are seeded to reproduce the prior flat model — ``weight_percent/100 ×
AGENT_COMMISSION_SHARE`` — so switching to the table changes no accrued amount (D30). This
mirrors the D14 Trust-Score-Weights CRUD; the Phase-18 admin pricing API builds on it.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, String, UniqueConstraint

from main.app.core.state.status import AgentRole, VerificationTier
from main.appodus_utils import BaseEntity, BaseQueryDto, Object, PageRequest

# Basis points per whole percent (1% = 100 bps); a full 100% = 10_000 bps.
BPS_PER_PERCENT = 100
FULL_BPS = 10_000


# ─── ORM ──────────────────────────────────────────────────────────

class CommissionRule(BaseEntity):
    __tablename__ = "commission_rules"

    role = Column(String(16), nullable=False)
    tier = Column(String(16), nullable=False)
    # Agent share of the tier price for this role, in basis points (exact kobo math).
    rate_bps = Column(Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("role", "tier", name="uq_commission_rule_role_tier"),
    )


# ─── DTOs ─────────────────────────────────────────────────────────

class CreateCommissionRuleDto(Object):
    role: AgentRole
    tier: VerificationTier
    rate_bps: int


class UpdateCommissionRuleDto(Object):
    rate_bps: Optional[int] = None


class QueryCommissionRuleDto(BaseQueryDto):
    role: Optional[str] = None
    tier: Optional[str] = None


class SearchCommissionRuleDto(PageRequest, BaseQueryDto):
    tier: Optional[str] = None


class CommissionRuleDto(Object):
    id: str
    role: AgentRole
    tier: VerificationTier
    rate_bps: int
    date_created: datetime


class SetCommissionRuleDto(Object):
    """Admin sets a single (role × tier) rate, in basis points."""

    rate_bps: int

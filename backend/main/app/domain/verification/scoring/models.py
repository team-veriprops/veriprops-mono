"""Trust Score Weights domain (PRD §8.3, §18.5 — built early per decision-log D14).

The composite trust score on a released report is a weighted blend of the per-role
review quality, using admin-defined weights per (tier × role) that must sum to 100%
within each tier. This is the config surface; the composite is computed at release
(§8.6 — recomputed only at release) by ``compute_composite``.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, String, UniqueConstraint

from main.app.core.state.status import AgentRole, VerificationTier
from main.appodus_utils import BaseEntity, BaseQueryDto, Object, PageRequest


# ─── ORM ──────────────────────────────────────────────────────────

class TrustScoreWeight(BaseEntity):
    __tablename__ = "trust_score_weight_config"

    tier = Column(String(16), nullable=False)
    role = Column(String(16), nullable=False)
    # Percent contribution of this role to the tier's composite (weights sum to 100/tier).
    weight_percent = Column(Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("tier", "role", name="uq_trust_weight_tier_role"),
    )


# ─── DTOs ─────────────────────────────────────────────────────────

class CreateTrustWeightDto(Object):
    tier: VerificationTier
    role: AgentRole
    weight_percent: int


class UpdateTrustWeightDto(Object):
    weight_percent: Optional[int] = None


class QueryTrustWeightDto(BaseQueryDto):
    tier: Optional[str] = None
    role: Optional[str] = None


class SearchTrustWeightDto(PageRequest, BaseQueryDto):
    tier: Optional[str] = None


class TrustWeightDto(Object):
    id: str
    tier: VerificationTier
    role: AgentRole
    weight_percent: int
    date_created: datetime


class TierWeightsDto(Object):
    """All role weights for one tier, with the running sum (must equal 100 to be valid)."""

    tier: VerificationTier
    weights: list[TrustWeightDto]
    total_percent: int
    valid: bool


class SetTierWeightsDto(Object):
    """Admin sets the full weight map for a tier in one call (§8.3 sum-to-100 enforced)."""

    weights: dict[AgentRole, int]

"""Trust score computation models — S30."""
from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal
from typing import Dict, Optional

from sqlalchemy import Column, Numeric, String, Text, UniqueConstraint

from main.appodus_utils import BaseEntity, Object
from main.appodus_utils.db.models import UTCDateTime


class TrustScoreWeightConfig(BaseEntity):
    """Per-tier, per-role weight (stored as percentage 0–100, must sum to 100 per tier)."""

    __tablename__ = "trust_score_weight_config"

    tier = Column(String(16), nullable=False, index=True)
    role = Column(String(16), nullable=False)
    weight = Column(Numeric(6, 3), nullable=False, default=0)
    updated_by = Column(String(36), nullable=True)

    __table_args__ = (
        UniqueConstraint("tier", "role", name="uq_ts_weight_tier_role"),
    )


class TrustScoreBreakdown(BaseEntity):
    """Snapshot of each scoring computation for audit purposes."""

    __tablename__ = "trust_score_breakdowns"

    verification_id = Column(String(36), nullable=False, index=True)
    task_scores_json = Column(Text, nullable=False)   # JSON: {role: score}
    weights_json = Column(Text, nullable=False)        # JSON: {role: weight}
    computed_score = Column(Numeric(5, 2), nullable=False)
    computed_at = Column(UTCDateTime, nullable=False)


# ─── DTOs ─────────────────────────────────────────────────────────────────────


class TrustScoreWeightDto(Object):
    id: str
    tier: str
    role: str
    weight: Decimal
    updated_by: Optional[str] = None
    updated_at: Optional[datetime] = None


class UpdateWeightDto(Object):
    weight: Optional[Decimal] = None
    updated_by: Optional[str] = None


class SetTierWeightsDto(Object):
    """Payload to update all role weights for a given tier at once."""
    weights: Dict[str, Decimal]  # {role: weight}; must sum to 100


class CreateWeightConfigDto(Object):
    tier: str
    role: str
    weight: Decimal
    updated_by: Optional[str] = None


class CreateBreakdownDto(Object):
    verification_id: str
    task_scores_json: str
    weights_json: str
    computed_score: Decimal
    computed_at: datetime


class TrustScoreBreakdownDto(Object):
    id: str
    verification_id: str
    task_scores_json: str
    weights_json: str
    computed_score: Decimal
    computed_at: datetime

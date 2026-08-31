"""Handoff token domain (PRD §7.5, §7.4.2).

A `jti` ledger. The token itself is stateless (a signed JWT); this table is what makes it
**single-use** — a redemption claims its nonce here, and a second attempt collides.
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, UniqueConstraint

from main.appodus_utils import BaseEntity, BaseQueryDto, InternalPageRequest, Object
from main.appodus_utils.db.models import UTCDateTime


class HandoffIntent(str, enum.Enum):
    """The one action a token authorizes (PRD §7.4.2).

    Deliberately closed and small: a token names an intent and a case, and nothing in the
    system will honour it for anything else.
    """

    PAY = "pay"
    UPLOAD = "upload"
    REPORT = "report"


# ─── ORM ──────────────────────────────────────────────────────────

class HandoffTokenRedemption(BaseEntity):
    __tablename__ = "handoff_token_redemptions"

    # The token's single-use nonce. The unique constraint is the enforcement mechanism,
    # not bookkeeping: two concurrent redemptions race here and exactly one wins.
    jti = Column(String(64), nullable=False)
    intent = Column(String(10), nullable=False)
    case_id = Column(String(36), nullable=False)
    customer_id = Column(String(36), nullable=True)
    redeemed_at = Column(UTCDateTime, nullable=False)
    # Kept for the §7.11 pen-check trail: which client actually burned the link.
    redeemed_ip = Column(String(45), nullable=True)

    __table_args__ = (
        UniqueConstraint("jti", name="uq_handoff_token_redemptions_jti"),
    )


# ─── DTOs ─────────────────────────────────────────────────────────

class CreateHandoffTokenRedemptionDto(Object):
    jti: str
    intent: HandoffIntent
    case_id: str
    customer_id: Optional[str] = None
    redeemed_at: datetime
    redeemed_ip: Optional[str] = None


class UpdateHandoffTokenRedemptionDto(Object):
    pass


class QueryHandoffTokenRedemptionDto(BaseQueryDto):
    jti: Optional[str] = None
    case_id: Optional[str] = None


class SearchHandoffTokenRedemptionDto(InternalPageRequest, BaseQueryDto):
    case_id: Optional[str] = None

"""Handoff token domain (PRD §26.5, §26.4.2).

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
    """The one action a token authorizes (PRD §26.4.2, §26.4.4).

    Deliberately closed and small: a token names an intent and a subject, and nothing in
    the system will honour it for anything else.

    The set has two shapes, and they are mutually exclusive by construction (D55). The
    three **action** intents name a case and the customer who owns it. ``LINK`` and
    ``INTAKE`` name a phone number and nothing else — both are minted for a WhatsApp
    number that has no account yet, so there is no customer to name and no case to scope
    to. ``INTAKE``'s collected answers stay server-side on the bot session (D71); the
    token carries none of them, so a forwarded link cannot leak someone's property details
    and the URL stays short enough for a chat message.
    """

    PAY = "pay"
    UPLOAD = "upload"
    REPORT = "report"
    LINK = "link"
    INTAKE = "intake"


# The intents that act on a case. Membership is what the claim-shape validator keys on,
# so a fourth action intent added above is covered by simply being listed here.
ACTION_INTENTS = frozenset({HandoffIntent.PAY, HandoffIntent.UPLOAD, HandoffIntent.REPORT})


# ─── ORM ──────────────────────────────────────────────────────────

class HandoffTokenRedemption(BaseEntity):
    __tablename__ = "handoff_token_redemptions"

    # The token's single-use nonce. The unique constraint is the enforcement mechanism,
    # not bookkeeping: two concurrent redemptions race here and exactly one wins.
    jti = Column(String(64), nullable=False)
    intent = Column(String(10), nullable=False)
    # Null for a phone-scoped token (`link`/`intake`), which names a number rather than
    # a case (D55, D71).
    case_id = Column(String(36), nullable=True)
    customer_id = Column(String(36), nullable=True)
    # The number a phone-scoped token was minted for — the other half of the pen-check
    # trail when the redemption names no case.
    phone_e164 = Column(String(32), nullable=True)
    redeemed_at = Column(UTCDateTime, nullable=False)
    # Kept for the §26.11 pen-check trail: which client actually burned the link.
    redeemed_ip = Column(String(45), nullable=True)

    __table_args__ = (
        UniqueConstraint("jti", name="uq_handoff_token_redemptions_jti"),
    )


# ─── DTOs ─────────────────────────────────────────────────────────

class CreateHandoffTokenRedemptionDto(Object):
    jti: str
    intent: HandoffIntent
    case_id: Optional[str] = None
    customer_id: Optional[str] = None
    phone_e164: Optional[str] = None
    redeemed_at: datetime
    redeemed_ip: Optional[str] = None


class UpdateHandoffTokenRedemptionDto(Object):
    pass


class QueryHandoffTokenRedemptionDto(BaseQueryDto):
    jti: Optional[str] = None
    case_id: Optional[str] = None


class SearchHandoffTokenRedemptionDto(InternalPageRequest, BaseQueryDto):
    case_id: Optional[str] = None

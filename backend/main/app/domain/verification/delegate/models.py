"""Per-case delegate (PRD §7.4.5, Decision O, D67; WA-26).

The buyer's answer to "my brother is handling this for me". §7.4.5 exists because that
sentence is a social-engineering script, and the bot has to be able to refuse it without
being useless — which it can only do if there is a legitimate way for the account holder
to say yes. A delegate is that way, and it is deliberately the narrowest grant that is
still worth having:

* **One per case, authorized by the owner, from the case page.** Not an account-level
  grant, so it cannot follow the delegate onto a second verification.
* **OTP-verified before anything is visible.** `verified_at` is null until they prove
  control of the number, and an unverified row resolves to nothing.
* **Status milestones only.** Never documents, reports, chat history or intake data —
  which is structural rather than enforced: the delegate audience sends the
  `delegate_status` template, and that template has no link parameter to fill.
* **Revocable instantly, effective on the next event**, because the audience is resolved
  at send time rather than stored on anything.

`phone_e164` is the delegate's own column and never touches `whatsapp_links` (D67). Reusing
the link table would either break its one-account-one-number constraint or hand a delegate
an account-shaped identity — and the bot's resolution order (account first, delegate
second) depends on the two being separable.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Index, String

from main.appodus_utils import BaseEntity, BaseQueryDto, InternalPageRequest, Object
from main.appodus_utils.db.models import UTCDateTime


# ─── ORM ──────────────────────────────────────────────────────────

class CaseDelegate(BaseEntity):
    __tablename__ = "case_delegates"

    verification_id = Column(String(36), nullable=False)
    # What the bot calls them, and what the case page shows the buyer.
    name = Column(String(120), nullable=False)
    # The delegate's own number, verified through the E1 OTP mechanics with a narrower
    # grant. Never written to `whatsapp_links` (D67).
    phone_e164 = Column(String(32), nullable=False)
    # Null until the OTP is confirmed. Nothing is visible before that moment: an
    # authorization the delegate never answered is an attempt, not a grant.
    verified_at = Column(UTCDateTime, nullable=True)
    revoked_at = Column(UTCDateTime, nullable=True)
    revoked_reason = Column(String(120), nullable=True)

    __table_args__ = (
        Index("ix_case_delegates_verification", "verification_id"),
        Index("ix_case_delegates_phone", "phone_e164"),
    )

    @property
    def active(self) -> bool:
        """Verified and not revoked — the only state that grants anything."""
        return self.verified_at is not None and self.revoked_at is None


# ─── DTOs ─────────────────────────────────────────────────────────

class CreateCaseDelegateDto(Object):
    verification_id: str
    name: str
    phone_e164: str


class UpdateCaseDelegateDto(Object):
    """Text fields only. The lifecycle timestamps are set on the attached row, because
    the update path stringifies datetimes and a timestamp column will not take one."""

    name: Optional[str] = None
    revoked_reason: Optional[str] = None


class QueryCaseDelegateDto(BaseQueryDto):
    verification_id: Optional[str] = None
    phone_e164: Optional[str] = None


class SearchCaseDelegateDto(InternalPageRequest, BaseQueryDto):
    verification_id: Optional[str] = None


# ─── Wire DTOs ────────────────────────────────────────────────────

class AuthorizeCaseDelegateDto(Object):
    """The buyer nominates someone. The case comes from the path, never from here."""

    name: str
    phone_e164: str


class ConfirmCaseDelegateDto(Object):
    code: str


class CaseDelegateDto(Object):
    """What the case page renders.

    Carries the number the buyer typed — they need to check it — but nothing about the
    delegate beyond what the buyer supplied, because there is nothing else to know: a
    delegate is not an account.
    """

    id: Optional[str] = None
    name: str
    phone_e164: str
    verified: bool = False
    verified_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    revoked_reason: Optional[str] = None


class CaseDelegateChallengeDto(Object):
    """The result of authorizing: where the code went, and for how long."""

    phone_e164: str
    resend_after_seconds: int

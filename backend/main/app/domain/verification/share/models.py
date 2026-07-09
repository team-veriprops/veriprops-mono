"""Report sharing domain (PRD §13.2) — child of the verification domain.

A ``VerificationShare`` is a tokenised, revocable, time-limited grant of visibility into a
released report beyond the owning customer:

- ``LINK_SUMMARY`` — anyone with the link sees the public *summary*.
- ``NAMED_FULL`` — a specific email recipient sees the *full* report after a one-time
  disclaimer acknowledgement.

Private (default) = no share rows and ``public_lookup_enabled`` off. Public = the
verification's ``public_lookup_enabled`` flag, surfaced by the VID lookup (§13.1).
"""
from __future__ import annotations

import enum
from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import Column, Index, String

from main.app.core.state.status import ShareType, VerificationTier
from main.app.domain.property.models import PropertyType
from main.app.domain.verification.report.models import CustomerReportDto
from main.appodus_utils import BaseEntity, BaseQueryDto, Object, InternalPageRequest
from main.appodus_utils.db.models import UTCDateTime


# ─── ORM ──────────────────────────────────────────────────────────

class VerificationShare(BaseEntity):
    __tablename__ = "verification_shares"

    verification_id = Column(String(36), nullable=False, index=True)
    share_type = Column(String(16), nullable=False)
    # Bearer capability: the unguessable token IS the authorization for the link. Stored
    # raw (not hashed) so the customer can re-copy the link from the share list.
    token = Column(String(64), nullable=False, unique=True, index=True)
    recipient_email = Column(String(254), nullable=True)  # NAMED_FULL only
    expires_at = Column(UTCDateTime, nullable=True)
    revoked_at = Column(UTCDateTime, nullable=True)
    first_viewed_at = Column(UTCDateTime, nullable=True)
    disclaimer_acked_at = Column(UTCDateTime, nullable=True)  # NAMED_FULL first-view gate

    __table_args__ = (
        Index("ix_verification_shares_verification", "verification_id"),
    )


# ─── Public lookup result (§13.1 state routing) ───────────────────

class PublicLookupState(str, enum.Enum):
    """The five public-lookup outcomes (§13.1)."""

    SHARED = "SHARED"            # summary available
    PRIVATE = "PRIVATE"          # completed but not shared publicly ("not enabled")
    IN_PROGRESS = "IN_PROGRESS"  # verification still running
    DISPUTED = "DISPUTED"        # under dispute review
    NOT_FOUND = "NOT_FOUND"      # unknown / never a shareable outcome


# ─── DTOs ─────────────────────────────────────────────────────────

class CreateVerificationShareDto(Object):
    verification_id: str
    share_type: ShareType
    token: str
    recipient_email: Optional[str] = None


class UpdateVerificationShareDto(Object):
    revoked_at: Optional[datetime] = None
    first_viewed_at: Optional[datetime] = None
    disclaimer_acked_at: Optional[datetime] = None


class QueryVerificationShareDto(BaseQueryDto):
    verification_id: Optional[str] = None
    token: Optional[str] = None


class SearchVerificationShareDto(InternalPageRequest, BaseQueryDto):
    verification_id: Optional[str] = None


class CreateShareRequestDto(Object):
    """Customer request to create a share (§13.2)."""

    share_type: ShareType
    recipient_email: Optional[str] = None  # required for NAMED_FULL
    expires_in_days: Optional[int] = None  # defaults to the 30-day config knob


class PublicVisibilityDto(Object):
    enabled: bool


class ShareDto(Object):
    id: str
    verification_id: str
    share_type: ShareType
    recipient_email: Optional[str] = None
    token: str
    share_url: str
    expires_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    first_viewed_at: Optional[datetime] = None
    disclaimer_acked_at: Optional[datetime] = None
    active: bool = True
    date_created: datetime


class PublicSummaryDto(Object):
    """The unauthenticated summary (§13.1). Summary only — never full address, agent/owner
    names, documents, or the numeric trust score."""

    state: PublicLookupState
    message: Optional[str] = None
    vid: Optional[str] = None
    verified: bool = False
    trust_band: Optional[str] = None      # band string only, never the number
    tier: Optional[VerificationTier] = None
    property_type: Optional[PropertyType] = None
    state_region: Optional[str] = None    # property state (not the full address)
    lga: Optional[str] = None
    report_version: Optional[int] = None
    report_date: Optional[date] = None


class SharedReportDto(Object):
    """A tokenised share view (§13.2). Summary for LINK_SUMMARY; full report for a
    NAMED_FULL recipient once the disclaimer is acknowledged."""

    state: PublicLookupState
    share_type: Optional[ShareType] = None
    requires_acknowledgement: bool = False
    summary: Optional[PublicSummaryDto] = None
    report: Optional[CustomerReportDto] = None

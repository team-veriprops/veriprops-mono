"""Analytics DTOs (PRD §18.1) — orchestration-only, no ORM entity.

Every figure is derived server-side from the operational tables (backend is the source
of truth); the admin dashboard renders them, never computes them.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from main.app.core.state.status import VerificationTier
from main.appodus_utils import Object


class FunnelDto(Object):
    """Conversion funnel (§18.1): how many verifications reach each lifecycle stage."""

    created: int = 0
    submitted: int = 0
    paid: int = 0
    completed: int = 0
    submit_rate: float = 0.0     # submitted / created
    payment_rate: float = 0.0    # paid / submitted
    completion_rate: float = 0.0  # completed / paid


class TierTimeDto(Object):
    tier: VerificationTier
    avg_days: float = 0.0
    completed_count: int = 0


class TierRevenueDto(Object):
    tier: VerificationTier
    revenue_minor: int = 0
    count: int = 0


class LocationRevenueDto(Object):
    state: str
    revenue_minor: int = 0
    count: int = 0


class RevenueDto(Object):
    total_minor: int = 0
    by_tier: List[TierRevenueDto] = []
    by_location: List[LocationRevenueDto] = []


class RegionalRowDto(Object):
    state: str
    active: int = 0
    completed: int = 0
    avg_trust_score: Optional[float] = None
    revenue_minor: int = 0


class AgentTrendPointDto(Object):
    month: str            # "YYYY-MM"
    completed_tasks: int = 0
    avg_quality: Optional[float] = None


class AgentTrendsDto(Object):
    points: List[AgentTrendPointDto] = []


# ─── WhatsApp channel (§7.10, WA-43) ──────────────────────────────


class ChannelCountDto(Object):
    """One bar in a §7.10 breakdown — a page code, or an escalation reason."""

    label: str
    count: int


class WhatsAppNumberHealthDto(Object):
    """Meta's verdict on our sending number (§7.10, D81).

    `synced_at` is rendered beside the rating rather than hidden, because a GREEN we have
    not been able to refresh for a week is a different fact from a GREEN from this morning
    — and `sync_error` is what says which of the two you are looking at.
    """

    quality_rating: str
    messaging_limit_tier: Optional[str] = None
    synced_at: Optional[datetime] = None
    sync_error: Optional[str] = None


class WhatsAppChannelAnalyticsDto(Object):
    """§7.10's seven metrics over one window (WA-43).

    Counts and rates are both returned. The rate is the number §7.10 asks for, and the
    counts behind it are what makes a rate readable — "60%" over three conversations is a
    very different thing from the same figure over three hundred, and an admin who cannot
    see which is being shown will act on the wrong one.
    """

    window_days: int

    # Seam conversion — §7.10's headline: "the cost of the A1 trust boundary, measured."
    intake_completed: int = 0
    payment_completed: int = 0
    seam_conversion_rate: float = 0.0

    # Channel demand, and where it came from.
    enquiries: int = 0
    enquiries_by_page_code: List[ChannelCountDto] = []

    # Bot flow effectiveness.
    intake_started: int = 0
    enquiry_to_intake_rate: float = 0.0

    # Bot coverage gaps — the rate, and the reasons that say what to build next.
    escalations: int = 0
    escalation_rate: float = 0.0
    escalations_by_reason: List[ChannelCountDto] = []

    # Consent asset growth (§7.4.6). Denominator is ACTIVE linked numbers (D84): of the
    # customers this channel can actually reach, how many said yes.
    linked_numbers: int = 0
    utility_opt_ins: int = 0
    marketing_opt_ins: int = 0
    utility_opt_in_rate: float = 0.0
    marketing_opt_in_rate: float = 0.0

    # Platform-dependency early warning, and v1.1 transcription-assist trigger data.
    number_health: Optional[WhatsAppNumberHealthDto] = None
    voice_notes: int = 0

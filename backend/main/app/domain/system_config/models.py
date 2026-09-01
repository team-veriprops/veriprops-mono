"""System configuration domain (PRD §14, §18.5 / D28) — a typed key-value settings store."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Column, String, Text

from main.appodus_utils import BaseEntity, BaseQueryDto, Object, InternalPageRequest
from main.appodus_utils.db.models import JSONB_VARIANT


class ConfigKey(str, enum.Enum):
    """The admin-editable operational knobs used by §14. Referenced via this enum, never
    as free string literals."""

    DISPUTE_WINDOW_DAYS = "dispute_window_days"          # §14.3 dispute window after COMPLETED
    RECHECK_PRICE_PCT = "recheck_price_pct"              # §14.1 re-check fee = pct of original (D26)
    AGENT_DISPUTE_DEFENCE_HOURS = "agent_dispute_defence_hours"  # §14.3 agent defence window
    # §15.2 commission clearance / reserve (S19)
    COMMISSION_CLEARANCE_DAYS = "commission_clearance_days"      # days a commission clears (bulk → available)
    COMMISSION_RESERVE_PCT = "commission_reserve_pct"            # % held back until the chargeback window closes
    CHARGEBACK_WINDOW_DAYS = "chargeback_window_days"            # card-chargeback window (reserve release)
    # §16.1 agent reputation / timeliness (S20)
    TASK_SLA_HOURS = "task_sla_hours"                            # per-task turnaround target (timeliness metric)
    AGENT_LOW_PERFORMANCE_THRESHOLD = "agent_low_performance_threshold"   # composite below → reduced job feed
    AGENT_TOP_AGENT_ACCURACY_THRESHOLD = "agent_top_agent_accuracy_threshold"  # accuracy at/above → Top Agent
    AGENT_WIDE_COVERAGE_STATES = "agent_wide_coverage_states"    # coverage state-count above → flagged for review
    # §17.1 growth & conversion (S21)
    FIRST_TIME_DISCOUNT_PERCENT = "first_time_discount_percent"  # auto discount on a customer's first verification
    REFERRAL_CREDIT_NGN = "referral_credit_ngn"                  # referrer credit (whole NGN) on invitee's first payment
    MAX_DISCOUNT_PERCENT = "max_discount_percent"                # combined discount cap (first-time + referral)
    CANCELLATION_SURCHARGE_PCT = "cancellation_surcharge_pct"    # surcharge on cancellation after assignment
    # §19 audit & compliance maturity (S23)
    PII_RETENTION_DAYS = "pii_retention_days"                    # PII retention before the NDPA erasure window (§19.2)
    ERASURE_REQUEST_REVIEW_SLA_DAYS = "erasure_request_review_sla_days"  # SLA to review a data-erasure request (§19.1)
    # Operational SLA / product knobs (admin-tunable without a redeploy)
    SLA_AT_RISK_DAYS = "sla_at_risk_days"                        # dashboard horizon: active verifications due within N days count as at-risk (§18.1)
    PAYOUT_SLA_BUSINESS_DAYS = "payout_sla_business_days"        # target business days to settle an approved payout
    DISPUTE_MIN_DESCRIPTION_CHARS = "dispute_min_description_chars"  # minimum characters required to file a dispute
    SHARE_LINK_DEFAULT_EXPIRY_DAYS = "share_link_default_expiry_days"  # default lifetime of a report share link
    ANALYTICS_TREND_MONTHS = "analytics_trend_months"           # trailing months included in analytics trend series
    # §7 human coverage (Decision G / D68) — the hours the bot promises a person, in WAT.
    # Admin-tunable because a rota change must not need a redeploy.
    SUPPORT_HOURS_START = "support_hours_start"                 # first staffed hour, 24h WAT
    SUPPORT_HOURS_END = "support_hours_end"                     # last staffed hour on a weekday, 24h WAT
    SUPPORT_SATURDAY_END = "support_saturday_end"               # last staffed hour on Saturday (Sunday: none)
    OFFLINE_RESPONSE_HOURS = "offline_response_hours"           # response time the bot states outside cover


# Seeded defaults (idempotent, by migration 0001). Values are stored as JSON scalars.
CONFIG_DEFAULTS: dict[ConfigKey, Any] = {
    ConfigKey.DISPUTE_WINDOW_DAYS: 30,
    ConfigKey.RECHECK_PRICE_PCT: 30,
    ConfigKey.AGENT_DISPUTE_DEFENCE_HOURS: 48,
    ConfigKey.COMMISSION_CLEARANCE_DAYS: 7,
    ConfigKey.COMMISSION_RESERVE_PCT: 10,
    ConfigKey.CHARGEBACK_WINDOW_DAYS: 120,
    ConfigKey.TASK_SLA_HOURS: 48,
    ConfigKey.AGENT_LOW_PERFORMANCE_THRESHOLD: 40,
    ConfigKey.AGENT_TOP_AGENT_ACCURACY_THRESHOLD: 90,
    ConfigKey.AGENT_WIDE_COVERAGE_STATES: 6,
    ConfigKey.FIRST_TIME_DISCOUNT_PERCENT: 10,
    ConfigKey.REFERRAL_CREDIT_NGN: 5_000,
    ConfigKey.MAX_DISCOUNT_PERCENT: 25,
    ConfigKey.CANCELLATION_SURCHARGE_PCT: 20,
    ConfigKey.PII_RETENTION_DAYS: 2555,  # ≈ 7 years
    ConfigKey.ERASURE_REQUEST_REVIEW_SLA_DAYS: 30,
    ConfigKey.SLA_AT_RISK_DAYS: 2,
    ConfigKey.PAYOUT_SLA_BUSINESS_DAYS: 2,
    ConfigKey.DISPUTE_MIN_DESCRIPTION_CHARS: 100,
    ConfigKey.SHARE_LINK_DEFAULT_EXPIRY_DAYS: 30,
    ConfigKey.ANALYTICS_TREND_MONTHS: 6,
    # Decision G: 8am–8pm WAT weekdays, Saturday morning to 1pm, no Sunday cover.
    ConfigKey.SUPPORT_HOURS_START: 8,
    ConfigKey.SUPPORT_HOURS_END: 20,
    ConfigKey.SUPPORT_SATURDAY_END: 13,
    ConfigKey.OFFLINE_RESPONSE_HOURS: 12,
}

CONFIG_DESCRIPTIONS: dict[ConfigKey, str] = {
    ConfigKey.DISPUTE_WINDOW_DAYS: "Days after a report is completed during which a dispute may be filed.",
    ConfigKey.RECHECK_PRICE_PCT: "Re-check fee as a percentage of the original tier price.",
    ConfigKey.AGENT_DISPUTE_DEFENCE_HOURS: "Hours an agent has to respond to a dispute targeting their task.",
    ConfigKey.COMMISSION_CLEARANCE_DAYS: "Days after task approval before the bulk of a commission becomes withdrawable.",
    ConfigKey.COMMISSION_RESERVE_PCT: "Percentage of a commission retained in reserve until the chargeback window closes.",
    ConfigKey.CHARGEBACK_WINDOW_DAYS: "Card-chargeback window; the commission reserve is released only after it passes.",
    ConfigKey.TASK_SLA_HOURS: "Target hours from task acceptance to submission, used for the agent timeliness metric.",
    ConfigKey.AGENT_LOW_PERFORMANCE_THRESHOLD: "Composite score below which an agent's job-feed visibility is reduced.",
    ConfigKey.AGENT_TOP_AGENT_ACCURACY_THRESHOLD: "Accuracy score at/above which an agent earns the Top Agent badge.",
    ConfigKey.AGENT_WIDE_COVERAGE_STATES: "Number of declared coverage states above which coverage is flagged for admin review.",
    ConfigKey.FIRST_TIME_DISCOUNT_PERCENT: "Percentage auto-discount applied to a customer's first verification.",
    ConfigKey.REFERRAL_CREDIT_NGN: "Referrer credit, in whole NGN, earned when an invitee's first payment clears.",
    ConfigKey.MAX_DISCOUNT_PERCENT: "Cap on the combined first-time + referral discount as a percentage of the price.",
    ConfigKey.CANCELLATION_SURCHARGE_PCT: "Surcharge percentage applied when a verification is cancelled after assignment.",
    ConfigKey.PII_RETENTION_DAYS: "Days personal data is retained before it is eligible for NDPA erasure (pseudonymisation).",
    ConfigKey.ERASURE_REQUEST_REVIEW_SLA_DAYS: "Target days for an admin to review a submitted data-erasure request.",
    ConfigKey.SLA_AT_RISK_DAYS: "Active verifications due within this many days are flagged as SLA-at-risk on the admin dashboard.",
    ConfigKey.PAYOUT_SLA_BUSINESS_DAYS: "Target number of business days to settle an approved agent payout.",
    ConfigKey.DISPUTE_MIN_DESCRIPTION_CHARS: "Minimum characters a customer must provide when filing a dispute.",
    ConfigKey.SHARE_LINK_DEFAULT_EXPIRY_DAYS: "Default number of days a report share link stays valid before expiring.",
    ConfigKey.ANALYTICS_TREND_MONTHS: "Number of trailing months included in analytics trend series.",
    ConfigKey.SUPPORT_HOURS_START: "First staffed hour for human support, 24-hour clock, West Africa Time.",
    ConfigKey.SUPPORT_HOURS_END: "Last staffed hour on a weekday, 24-hour clock, West Africa Time.",
    ConfigKey.SUPPORT_SATURDAY_END: "Last staffed hour on Saturday (there is no Sunday cover).",
    ConfigKey.OFFLINE_RESPONSE_HOURS: "Response time the bot promises when it escalates outside staffed hours.",
}


# ─── ORM ──────────────────────────────────────────────────────────

class SystemConfig(BaseEntity):
    __tablename__ = "system_config"

    key = Column(String(64), nullable=False, unique=True, index=True)
    value_json = Column(JSONB_VARIANT, nullable=True)
    description = Column(Text, nullable=True)


# ─── DTOs ─────────────────────────────────────────────────────────

class CreateSystemConfigDto(Object):
    key: str
    value_json: Any = None
    description: Optional[str] = None


class UpdateSystemConfigDto(Object):
    value_json: Any = None
    description: Optional[str] = None


class QuerySystemConfigDto(BaseQueryDto):
    key: Optional[str] = None


class SearchSystemConfigDto(InternalPageRequest, BaseQueryDto):
    key: Optional[str] = None


class SystemConfigDto(Object):
    key: ConfigKey
    value: Any = None
    description: Optional[str] = None
    date_updated: Optional[datetime] = None


class SetConfigValueDto(Object):
    """Admin update of a single config value (typed loosely — coerced per key)."""

    value: Any

"""System configuration domain (PRD §14, §18.5 / D28) — a typed key-value settings store."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Column, String, Text

from main.appodus_utils import BaseEntity, BaseQueryDto, Object, PageRequest
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


# Seeded defaults (idempotent, via DataSeeder). Values are stored as JSON scalars.
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


class SearchSystemConfigDto(PageRequest, BaseQueryDto):
    key: Optional[str] = None


class SystemConfigDto(Object):
    key: ConfigKey
    value: Any = None
    description: Optional[str] = None
    date_updated: Optional[datetime] = None


class SetConfigValueDto(Object):
    """Admin update of a single config value (typed loosely — coerced per key)."""

    value: Any

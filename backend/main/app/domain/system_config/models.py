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


# Seeded defaults (idempotent, via DataSeeder). Values are stored as JSON scalars.
CONFIG_DEFAULTS: dict[ConfigKey, Any] = {
    ConfigKey.DISPUTE_WINDOW_DAYS: 30,
    ConfigKey.RECHECK_PRICE_PCT: 30,
    ConfigKey.AGENT_DISPUTE_DEFENCE_HOURS: 48,
}

CONFIG_DESCRIPTIONS: dict[ConfigKey, str] = {
    ConfigKey.DISPUTE_WINDOW_DAYS: "Days after a report is completed during which a dispute may be filed.",
    ConfigKey.RECHECK_PRICE_PCT: "Re-check fee as a percentage of the original tier price.",
    ConfigKey.AGENT_DISPUTE_DEFENCE_HOURS: "Hours an agent has to respond to a dispute targeting their task.",
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

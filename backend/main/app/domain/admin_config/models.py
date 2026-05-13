"""Admin-configurable system settings — keyed string values.

Stores operational knobs that admins can adjust without a deploy:
no_show_timeout_hours, pool_timeout_hours, auto_assignment_enabled.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, Text, UniqueConstraint

from main.appodus_utils import BaseEntity, BaseQueryDto, Object, PageRequest


class AdminConfig(BaseEntity):
    __tablename__ = "admin_config"

    key = Column(String(64), nullable=False)
    value = Column(Text, nullable=False)
    description = Column(String(255), nullable=True)
    updated_by = Column(String(36), nullable=True, index=True)

    __table_args__ = (
        UniqueConstraint("key", name="uq_admin_config_key"),
    )


# ─── DTOs ─────────────────────────────────────────────────────────────────────


class AdminConfigDto(Object):
    id: str
    key: str
    value: str
    description: Optional[str] = None
    updated_by: Optional[str] = None
    date_updated: Optional[datetime] = None


class CreateAdminConfigDto(Object):
    key: str
    value: str
    description: Optional[str] = None
    updated_by: Optional[str] = None


class UpdateAdminConfigDto(Object):
    value: Optional[str] = None
    description: Optional[str] = None
    updated_by: Optional[str] = None


class QueryAdminConfigDto(BaseQueryDto):
    key: Optional[str] = None


class SearchAdminConfigDto(PageRequest, BaseQueryDto):
    key: Optional[str] = None


class SetAdminConfigDto(Object):
    value: str

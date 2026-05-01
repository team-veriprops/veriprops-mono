"""Server-side resumable signup draft.

A draft is keyed on the user's email and persists their signup wizard state so
they can resume after closing the tab or switching device. Drafts are
short-lived (7 days) and cleared on successful signup.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import Column, DateTime, Index, Integer, String, Text

from main.appodus_utils import BaseEntity, BaseQueryDto, Object, PageRequest


class SignupDraft(BaseEntity):
    __tablename__ = "signup_drafts"

    # Email is the natural key for an unauthenticated draft. Stored normalised
    # (lowercased) — service layer enforces.
    email = Column(String(254), nullable=False, unique=True, index=True)
    step = Column(Integer, nullable=False, default=0)
    # JSON-encoded payload — opaque to the backend; the frontend wizard owns
    # the schema. Storing as TEXT keeps us DB-portable.
    payload = Column(Text, nullable=False, default="{}")
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)

    __table_args__ = (
        Index("ix_signup_drafts_email_active", "email", "expires_at"),
    )


# ─── DTOs ─────────────────────────────────────────────────────────


class CreateSignupDraftDto(Object):
    email: str
    step: int = 0
    payload: str = "{}"
    expires_at: datetime


class UpdateSignupDraftDto(Object):
    step: Optional[int] = None
    payload: Optional[str] = None
    expires_at: Optional[datetime] = None


class SearchSignupDraftDto(PageRequest, BaseQueryDto):
    email: Optional[str] = None


class QuerySignupDraftDto(BaseQueryDto):
    email: Optional[str] = None
    step: Optional[int] = None
    expires_at: Optional[datetime] = None


class SignupDraftDto(Object):
    """API representation. The `payload` is decoded to a dict for the
    frontend so it can resume the wizard directly."""
    email: str
    step: int
    payload: Dict[str, Any]
    updated_at: datetime

"""Audit log domain — PRD R0.10.

Append-only record of every state-machine transition and privileged action in the
system. Every service that mutates state must call AuditLogService.schedule(...)
inside its @transactional method so the row is committed atomically.
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import Column, Index, JSON, String

from main.appodus_utils import BaseEntity, BaseQueryDto, Object, PageRequest
from main.appodus_utils.db.models import UTCDateTime


class AuditActionType(str, enum.Enum):
    # ── Verification lifecycle ──────────────────────────────────────
    VERIFICATION_SUBMITTED = "VERIFICATION_SUBMITTED"
    VERIFICATION_STATE_CHANGED = "VERIFICATION_STATE_CHANGED"
    # ── Agent onboarding ───────────────────────────────────────────
    AGENT_APPLICATION_SUBMITTED = "AGENT_APPLICATION_SUBMITTED"
    AGENT_APPLICATION_APPROVED = "AGENT_APPLICATION_APPROVED"
    AGENT_APPLICATION_REJECTED = "AGENT_APPLICATION_REJECTED"
    # ── Admin operations ───────────────────────────────────────────
    ADMIN_INVITED = "ADMIN_INVITED"
    ADMIN_INVITE_ACCEPTED = "ADMIN_INVITE_ACCEPTED"
    ADMIN_ROLE_CHANGED = "ADMIN_ROLE_CHANGED"
    # ── Payment ────────────────────────────────────────────────────
    PAYMENT_INITIATED = "PAYMENT_INITIATED"
    PAYMENT_SUCCEEDED = "PAYMENT_SUCCEEDED"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    WIRE_PROOF_UPLOADED = "WIRE_PROOF_UPLOADED"
    WIRE_PROOF_CONFIRMED = "WIRE_PROOF_CONFIRMED"
    # ── Consent ────────────────────────────────────────────────────
    CONSENT_RECORDED = "CONSENT_RECORDED"
    # ── Tasks (enum pre-defined; wired by later slices) ───────────
    TASK_STATE_CHANGED = "TASK_STATE_CHANGED"
    TASK_ASSIGNED = "TASK_ASSIGNED"
    TASK_REASSIGNED = "TASK_REASSIGNED"
    # ── KYC ────────────────────────────────────────────────────────
    KYC_BVN_VERIFIED = "KYC_BVN_VERIFIED"
    KYC_SELFIE_RESOLVED = "KYC_SELFIE_RESOLVED"
    KYC_ADMIN_REVIEWED = "KYC_ADMIN_REVIEWED"


# ─── ORM ──────────────────────────────────────────────────────────────────────


class AuditLog(BaseEntity):
    __tablename__ = "audit_logs"

    # Who triggered the action; null = system-initiated
    actor_id = Column(String(36), nullable=True, index=True)
    action = Column(String(64), nullable=False, index=True)
    resource_type = Column(String(64), nullable=False, index=True)
    resource_id = Column(String(36), nullable=False, index=True)
    from_state = Column(String(32), nullable=True)
    to_state = Column(String(32), nullable=True)
    # Flexible extras: rejection reason, tier, ref numbers, etc.
    meta = Column(JSON, nullable=True)
    ip_address = Column(String(64), nullable=True)
    occurred_at = Column(UTCDateTime, nullable=False, index=True)

    __table_args__ = (
        # Composite index supports the per-resource audit-export query (R19.1)
        Index("ix_audit_logs_resource", "resource_type", "resource_id"),
    )


# ─── DTOs ─────────────────────────────────────────────────────────────────────


class CreateAuditLogDto(Object):
    actor_id: Optional[str] = None
    action: AuditActionType
    resource_type: str
    resource_id: str
    from_state: Optional[str] = None
    to_state: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    occurred_at: datetime


class UpdateAuditLogDto(Object):
    # Audit logs are append-only; no mutable fields in normal operation.
    pass


class SearchAuditLogDto(PageRequest, BaseQueryDto):
    actor_id: Optional[str] = None
    action: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None


class QueryAuditLogDto(BaseQueryDto):
    actor_id: Optional[str] = None
    action: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    from_state: Optional[str] = None
    to_state: Optional[str] = None
    occurred_at: Optional[datetime] = None

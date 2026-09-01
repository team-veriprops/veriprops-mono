"""Audit log domain — PRD R0.10.

Append-only record of every state-machine transition and privileged action in the
system. Every service that mutates state must call AuditLogService.schedule(...)
inside its @transactional method so the row is committed atomically.
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import Column, Index, String

from main.appodus_utils import BaseEntity, BaseQueryDto, Object, InternalPageRequest
from main.appodus_utils.db.models import UTCDateTime, JSONB_VARIANT


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
    # ── Admin user management (§4.2) ───────────────────────────────
    USER_SUSPENDED = "USER_SUSPENDED"
    USER_REACTIVATED = "USER_REACTIVATED"
    PASSWORD_RESET_FORCED = "PASSWORD_RESET_FORCED"
    TRUST_STATUS_CHANGED = "TRUST_STATUS_CHANGED"
    # ── Payment ────────────────────────────────────────────────────
    PAYMENT_INITIATED = "PAYMENT_INITIATED"
    PAYMENT_SUCCEEDED = "PAYMENT_SUCCEEDED"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    PAYMENT_REFUNDED = "PAYMENT_REFUNDED"
    WIRE_PROOF_UPLOADED = "WIRE_PROOF_UPLOADED"
    WIRE_PROOF_CONFIRMED = "WIRE_PROOF_CONFIRMED"
    # ── Chargeback (§6a) ───────────────────────────────────────────
    CHARGEBACK_FLAGGED = "CHARGEBACK_FLAGGED"
    CHARGEBACK_REBUTTAL_SUBMITTED = "CHARGEBACK_REBUTTAL_SUBMITTED"
    CHARGEBACK_WON = "CHARGEBACK_WON"
    CHARGEBACK_LOST = "CHARGEBACK_LOST"
    # ── Commission (§15.2) ─────────────────────────────────────────
    COMMISSION_ACCRUED = "COMMISSION_ACCRUED"
    COMMISSION_FROZEN = "COMMISSION_FROZEN"
    COMMISSION_UNFROZEN = "COMMISSION_UNFROZEN"
    COMMISSION_REVERSED = "COMMISSION_REVERSED"
    # ── Agent reputation & coverage (§16) ──────────────────────────
    AGENT_AVAILABILITY_CHANGED = "AGENT_AVAILABILITY_CHANGED"
    AGENT_COVERAGE_UPDATED = "AGENT_COVERAGE_UPDATED"
    # ── Payouts (§15.1) ────────────────────────────────────────────
    PAYOUT_REQUESTED = "PAYOUT_REQUESTED"
    PAYOUT_APPROVED = "PAYOUT_APPROVED"
    PAYOUT_HELD = "PAYOUT_HELD"
    PAYOUT_ADJUSTED = "PAYOUT_ADJUSTED"
    PAYOUT_REJECTED = "PAYOUT_REJECTED"
    PAYOUT_CANCELLED = "PAYOUT_CANCELLED"
    # ── Admin control panel (§6.1) ─────────────────────────────────
    VERIFICATION_PAUSED = "VERIFICATION_PAUSED"
    VERIFICATION_RESUMED = "VERIFICATION_RESUMED"
    VERIFICATION_CANCELLED = "VERIFICATION_CANCELLED"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    VERIFICATION_DELAYED = "VERIFICATION_DELAYED"
    ADMIN_NOTE_ADDED = "ADMIN_NOTE_ADDED"
    # ── Consent ────────────────────────────────────────────────────
    CONSENT_RECORDED = "CONSENT_RECORDED"
    # ── Tasks (enum pre-defined; wired by later slices) ───────────
    TASK_STATE_CHANGED = "TASK_STATE_CHANGED"
    TASK_ASSIGNED = "TASK_ASSIGNED"
    TASK_REASSIGNED = "TASK_REASSIGNED"
    TASK_ACCEPTED = "TASK_ACCEPTED"
    TASK_DECLINED = "TASK_DECLINED"
    TASK_STARTED = "TASK_STARTED"
    TASK_SUBMITTED = "TASK_SUBMITTED"
    EVIDENCE_CAPTURED = "EVIDENCE_CAPTURED"
    # ── Admin review & report release (§8) ────────────────────────
    TASK_APPROVED = "TASK_APPROVED"
    TASK_REJECTED = "TASK_REJECTED"
    TASK_REOPENED = "TASK_REOPENED"
    CONFLICT_DETECTED = "CONFLICT_DETECTED"
    REPORT_RELEASED = "REPORT_RELEASED"
    VERIFICATION_REFUNDED = "VERIFICATION_REFUNDED"
    # ── KYC ────────────────────────────────────────────────────────
    KYC_BVN_VERIFIED = "KYC_BVN_VERIFIED"
    KYC_SELFIE_RESOLVED = "KYC_SELFIE_RESOLVED"
    KYC_ADMIN_REVIEWED = "KYC_ADMIN_REVIEWED"
    # ── Admin config ───────────────────────────────────────────────
    ADMIN_CONFIG_CHANGED = "ADMIN_CONFIG_CHANGED"
    # ── Revision / re-verification / disputes (§14, S18) ───────────
    RECHECK_REQUESTED = "RECHECK_REQUESTED"
    RECHECK_APPROVED = "RECHECK_APPROVED"
    RECHECK_REJECTED = "RECHECK_REJECTED"
    RECHECK_STARTED = "RECHECK_STARTED"
    TIER_UPGRADE_REQUESTED = "TIER_UPGRADE_REQUESTED"
    TIER_UPGRADE_APPLIED = "TIER_UPGRADE_APPLIED"
    DISPUTE_OPENED = "DISPUTE_OPENED"
    DISPUTE_AGENT_DEFENDED = "DISPUTE_AGENT_DEFENDED"
    DISPUTE_RESOLVED = "DISPUTE_RESOLVED"
    # ── Communication layer (§11, S15) ─────────────────────────────
    MESSAGE_SENT = "MESSAGE_SENT"
    MESSAGE_HELD = "MESSAGE_HELD"
    MESSAGE_APPROVED = "MESSAGE_APPROVED"
    MESSAGE_REJECTED = "MESSAGE_REJECTED"
    # ── Conversational channels (§7.4.4) ───────────────────────────
    # The number a link named is recorded in `details`, so a released number is still
    # traceable after the link row has stopped holding it.
    WHATSAPP_NUMBER_LINKED = "WHATSAPP_NUMBER_LINKED"
    WHATSAPP_NUMBER_UNLINKED = "WHATSAPP_NUMBER_UNLINKED"
    # ── Data retention / erasure (S58) ─────────────────────────────
    DATA_ERASURE_REQUESTED = "DATA_ERASURE_REQUESTED"
    DATA_ERASURE_APPROVED = "DATA_ERASURE_APPROVED"
    DATA_ERASURE_REJECTED = "DATA_ERASURE_REJECTED"
    DATA_ERASURE_EXECUTED = "DATA_ERASURE_EXECUTED"


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
    details = Column(JSONB_VARIANT, nullable=True)
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
    details: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    occurred_at: datetime


class UpdateAuditLogDto(Object):
    # Audit logs are append-only; no mutable fields in normal operation.
    pass


class SearchAuditLogDto(InternalPageRequest, BaseQueryDto):
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


# ─── S56 read DTOs ────────────────────────────────────────────────────────────

class AuditEventDto(Object):
    """PII-safe event shown to customers and agents (no actor_id)."""
    action: str
    occurred_at: datetime
    from_state: Optional[str] = None
    to_state: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class AuditPackRowDto(Object):
    """Full row returned to admin for export / action-log view."""
    id: str
    actor_id: Optional[str] = None
    action: str
    resource_type: str
    resource_id: str
    from_state: Optional[str] = None
    to_state: Optional[str] = None
    occurred_at: datetime
    ip_address: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class AuditActivityPageDto(Object):
    items: List[AuditEventDto]
    total: int
    page: int
    page_size: int


class AdminActionLogPageDto(Object):
    items: List[AuditPackRowDto]
    total: int
    page: int
    page_size: int

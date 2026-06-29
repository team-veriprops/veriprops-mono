"""Idempotency-key ORM + DTOs (PRD §4.6).

One row per idempotency key. For client-supplied keys (entity creation, payment
initiation) the row reserves the operation and stores the response to replay; for
gateway webhooks the key is the gateway event id and the row records that the
event was already processed.
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import Column, Index, String, UniqueConstraint

from main.appodus_utils import BaseEntity, BaseQueryDto, Object
from main.appodus_utils.db.models import JSONB_VARIANT, UTCDateTime


class IdempotencyStatus(str, enum.Enum):
    PENDING = "PENDING"      # reserved; the operation is in flight
    COMPLETED = "COMPLETED"  # finished; response_snapshot/resource_id are final


# ─── ORM ──────────────────────────────────────────────────────────────────────


class IdempotencyKey(BaseEntity):
    __tablename__ = "idempotency_keys"

    # Client idempotency key or gateway event id. Unique across the table.
    key = Column(String(128), nullable=False)
    # Logical operation namespace, e.g. "payment.initiate", "verification.create",
    # "webhook.flutterwave" — lets the same raw key coexist across operations if needed.
    scope = Column(String(64), nullable=False)
    # Hash of the request body; detects the same key reused with a different payload.
    request_hash = Column(String(64), nullable=True)
    status = Column(String(16), nullable=False)
    # Stored response replayed verbatim on a duplicate call.
    response_snapshot = Column(JSONB_VARIANT, nullable=True)
    # Id of the resource the operation created (verification, payment, dispute, ...).
    resource_id = Column(String(36), nullable=True)
    expires_at = Column(UTCDateTime, nullable=False)

    __table_args__ = (
        UniqueConstraint("key", name="uq_idempotency_key"),
        Index("ix_idempotency_scope_expires", "scope", "expires_at"),
    )


# ─── DTOs ─────────────────────────────────────────────────────────────────────


class CreateIdempotencyKeyDto(Object):
    key: str
    scope: str
    status: IdempotencyStatus
    expires_at: datetime
    request_hash: Optional[str] = None
    response_snapshot: Optional[Dict[str, Any]] = None
    resource_id: Optional[str] = None


class UpdateIdempotencyKeyDto(Object):
    status: Optional[IdempotencyStatus] = None
    response_snapshot: Optional[Dict[str, Any]] = None
    resource_id: Optional[str] = None


class QueryIdempotencyKeyDto(BaseQueryDto):
    key: Optional[str] = None
    scope: Optional[str] = None
    status: Optional[str] = None

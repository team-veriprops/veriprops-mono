"""Domain events (PRD §4.8, §12.2).

One event type per meaningful thing that happens in the system. The enum covers the full
§12.2 trigger set; events whose source domains are not built yet (dispute / payout / re-check,
S18/S19) are declared here and in the rule table but not yet published (D21).
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Optional, Tuple


class EventType(str, enum.Enum):
    """Every domain event published on the §4.8 bus. Full §12.2 coverage (D21)."""

    # Customer lifecycle
    PAYMENT_CONFIRMED = "PAYMENT_CONFIRMED"
    STATUS_CHANGED = "STATUS_CHANGED"
    AGENTS_ASSIGNED = "AGENTS_ASSIGNED"
    EVIDENCE_ADDED = "EVIDENCE_ADDED"
    REPORT_READY = "REPORT_READY"
    REPORT_VERSIONED = "REPORT_VERSIONED"
    SLA_BREACHED = "SLA_BREACHED"
    REFUND_INITIATED = "REFUND_INITIATED"
    RECHECK_DECISION = "RECHECK_DECISION"      # source: S18 (declared, unfired)
    # Agent lifecycle
    NEW_JOB = "NEW_JOB"
    TASK_REASSIGNED = "TASK_REASSIGNED"
    TASK_REJECTED = "TASK_REJECTED"            # admin revision request
    PAYOUT_APPROVED = "PAYOUT_APPROVED"        # source: S19
    PAYOUT_HELD = "PAYOUT_HELD"                # source: S19
    COMMISSION_CLEARED = "COMMISSION_CLEARED"  # source: S19 — earnings moved to available (§15.1)
    # Admin lifecycle
    CONFLICT_FLAGGED = "CONFLICT_FLAGGED"
    AGENT_NO_SHOW = "AGENT_NO_SHOW"
    FRAUD_FLAGGED_MESSAGE = "FRAUD_FLAGGED_MESSAGE"
    DISPUTE_OPENED = "DISPUTE_OPENED"          # source: S18 (declared, unfired)
    DISPUTE_RESOLVED = "DISPUTE_RESOLVED"      # source: S18 (declared, unfired)
    PAYMENT_SETTLED = "PAYMENT_SETTLED"
    # Chat (§12.3 routing)
    MESSAGE_SENT = "MESSAGE_SENT"              # routine → Chat counter only (not a notification)


@dataclass
class DomainEvent:
    """A single published event.

    ``recipient_user_ids`` are the users to notify (in-app + per-user SSE). ``verification_id``
    scopes the verification-keyed SSE re-emit. ``sse_event`` preserves the exact S13 SSE event
    name so the ``RealtimeSubscriber`` re-emits it unchanged (frontend hooks are untouched).
    ``data`` carries SSE payload + notification/template context. ``type`` is optional: a pure
    UI-refresh nudge (SSE re-emit with no notification) carries only ``sse_event`` and leaves
    ``type`` as ``None`` — the notification subscriber skips it.
    """

    type: Optional[EventType] = None
    verification_id: Optional[str] = None
    recipient_user_ids: Tuple[str, ...] = ()
    actor_id: Optional[str] = None
    sse_event: Optional[str] = None
    data: dict = field(default_factory=dict)

"""Backend-owned notification copy + deep links (PRD §12.2, §N.4).

The frontend renders exactly what the backend produces — titles, bodies and in-app links are
never composed on the client (single source of truth). Links are plain route strings mirroring
`frontend/src/lib/routes.ts`; the surface is chosen from the event's primary audience.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from main.app.core.events.events import DomainEvent, EventType
from main.appodus_utils.integrations.messaging.models import MessageContext


def _portal_link(vid: Optional[str]) -> Optional[str]:
    return f"/portal/verifications/{vid}" if vid else None


def _admin_link(vid: Optional[str]) -> Optional[str]:
    return f"/admin/verifications/{vid}" if vid else None


# title, body-template, link-builder per event. Body may reference event.data via .format.
_CONTENT = {
    EventType.PAYMENT_CONFIRMED: ("Payment confirmed", "Your verification is now being processed.", _portal_link),
    EventType.STATUS_CHANGED: ("Verification updated", "Your verification status changed to {status}.", _portal_link),
    EventType.AGENTS_ASSIGNED: ("Agents assigned", "Our agents have started work on your verification.", _portal_link),
    EventType.EVIDENCE_ADDED: ("New evidence", "New evidence is available on your verification.", _portal_link),
    EventType.REPORT_READY: ("Report ready", "Your verification report is ready to view.", _portal_link),
    EventType.REPORT_VERSIONED: ("Report updated", "A new version of your report has been released.", _portal_link),
    EventType.SLA_BREACHED: ("Taking longer than planned", "Your verification is past its target date; we're on it.", _portal_link),
    EventType.REFUND_INITIATED: ("Refund initiated", "A refund has been initiated for your verification.", _portal_link),
    EventType.RECHECK_DECISION: ("Re-check decision", "There's an update on your re-check request.", _portal_link),
    EventType.NEW_JOB: ("New job available", "A new verification task is available for you.", lambda _v: "/agents/tasks"),
    EventType.TASK_REASSIGNED: ("Task reassigned", "One of your tasks has been reassigned.", lambda _v: "/agents/tasks"),
    EventType.TASK_REJECTED: ("Revision requested", "An admin has requested a revision on your task.", lambda _v: "/agents/tasks"),
    EventType.PAYOUT_APPROVED: ("Payout approved", "Your payout has been approved.", lambda _v: "/agents/payouts"),
    EventType.PAYOUT_HELD: ("Payout on hold", "Your payout is on hold pending review.", lambda _v: "/agents/payouts"),
    EventType.COMMISSION_CLEARED: ("Earnings available", "Funds have cleared and are now available to withdraw.", lambda _v: "/agents/earnings"),
    EventType.REFERRAL_CREDIT_EARNED: ("Referral credit earned", "A referral credit has cleared and is ready to use at checkout.", lambda _v: "/portal/referrals"),
    EventType.ABANDONMENT_RECOVERY: ("Finish your verification", "Your saved verification is waiting — pick up where you left off.", _portal_link),
    EventType.BROADCAST_ANNOUNCEMENT: ("Announcement", None, lambda _v: "/portal/notifications"),
    EventType.CONFLICT_FLAGGED: ("Conflict detected", "A conflict was flagged on a verification.", _admin_link),
    EventType.AGENT_NO_SHOW: ("Agent no-show", "An assigned agent did not accept in time.", _admin_link),
    EventType.FRAUD_FLAGGED_MESSAGE: ("Message held for review", "A message was flagged and is awaiting review.", lambda _v: "/admin/messages"),
    EventType.DISPUTE_OPENED: ("Dispute opened", "A dispute was opened on a verification.", _admin_link),
    EventType.DISPUTE_RESOLVED: ("Dispute resolved", "A dispute has been resolved.", _admin_link),
    EventType.PAYMENT_SETTLED: ("Payment settled", "A payment has settled.", _admin_link),
    EventType.ERASURE_STATUS_CHANGED: ("Data & privacy", "{message}", lambda _v: "/account/data-privacy"),
    # §4.2 admin user management — the suspension reason is admin-internal and never surfaces here.
    EventType.ACCOUNT_SUSPENDED: ("Account suspended", "Your account has been suspended. Contact support for assistance.", lambda _v: None),
    EventType.ACCOUNT_REACTIVATED: ("Account reactivated", "Your account is active again. Welcome back.", lambda _v: None),
}


def build_content(event: DomainEvent) -> Tuple[str, Optional[str], Optional[str]]:
    """Return (title, body, link) for an event's in-app notification."""
    entry = _CONTENT.get(event.type)
    if entry is None:
        return (event.type.value.replace("_", " ").title(), None, _portal_link(event.verification_id))
    title, body_tpl, link_fn = entry
    try:
        body = body_tpl.format(**event.data) if body_tpl else None
    except (KeyError, IndexError):
        body = body_tpl
    return title, body, link_fn(event.verification_id)


# Per-event context passed to the external (email/SMS) template — pulled from event.data.
_CONTEXT_KEYS = {
    EventType.STATUS_CHANGED: {MessageContext.VERIFICATION_NEW_STATUS.value: "status"},
    EventType.RECHECK_DECISION: {MessageContext.RECHECK_DECISION_OUTCOME.value: "decision"},
    EventType.DISPUTE_OPENED: {MessageContext.DISPUTE_VERIFICATION_ID.value: "vid"},
    EventType.DISPUTE_RESOLVED: {MessageContext.DISPUTE_RESOLUTION_OUTCOME.value: "outcome"},
    EventType.PAYOUT_HELD: {MessageContext.PAYOUT_HOLD_REASON.value: "reason"},
    EventType.ABANDONMENT_RECOVERY: {MessageContext.ABANDONMENT_VID.value: "vid"},
    EventType.BROADCAST_ANNOUNCEMENT: {
        MessageContext.BROADCAST_SUBJECT.value: "subject",
        MessageContext.BROADCAST_BODY_HTML.value: "body",
    },
}


def external_context(event: DomainEvent) -> Dict[str, Any]:
    """Template context for the external send, extracted from the event's data payload."""
    mapping = _CONTEXT_KEYS.get(event.type)
    if not mapping:
        return {}
    return {ctx_key: event.data[data_key] for ctx_key, data_key in mapping.items() if data_key in event.data}

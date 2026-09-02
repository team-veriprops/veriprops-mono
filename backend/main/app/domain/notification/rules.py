"""The single declarative Chat-vs-Notification rule table (PRD §4.8, §12.3).

One row per event type decides: does it become an in-app notification, which external
channels it may fan to (email/SMS, subject to per-user opt-out), and whether it is
*chat-only* (a routine message that bumps the Chat counter but never appears in
Notifications, FR-6/FR-7). The full §12.2 set is declared here; events whose source
domains are not built yet (dispute/payout/re-check) are declared but not yet published (D21).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from main.app.core.events.events import EventType
from main.appodus_utils.integrations.messaging.templating.models import AvailableTemplate


@dataclass(frozen=True)
class NotificationRule:
    """How one event surfaces. ``in_app`` is always on (§12.1); ``email``/``sms`` are the
    defaults a user may opt out of; ``chat_only`` suppresses the notification entirely
    (Chat counter only); ``template`` is the external-dispatch template (email/SMS).

    ``whatsapp`` marks the §7.6.2 milestones (D65). It is a **separate** channel with a
    **separate** template, because the §7.7 Meta template is not the email template and
    one field cannot be both. Two further things follow from `whatsapp=True`, and they are
    the reason it is a flag rather than a second table:

    * the customer's opt-in (§7.4.6) is checked in the router before the send, never at a
      send site — that is the WA-16/WA-27 property; and
    * an authorized delegate on the same case receives the milestone too, as
      `delegate_status` and never as this template (§7.4.5).
    """

    in_app: bool = True
    email: bool = False
    sms: bool = False
    chat_only: bool = False
    template: Optional[AvailableTemplate] = None
    whatsapp: bool = False
    whatsapp_template: Optional[AvailableTemplate] = None


_T = AvailableTemplate
RULES: Dict[EventType, NotificationRule] = {
    # Customer
    EventType.PAYMENT_CONFIRMED: NotificationRule(
        email=True, sms=True, template=_T.VERIFICATION_PAYMENT_CONFIRMED,
        whatsapp=True, whatsapp_template=_T.WHATSAPP_PAYMENT_CONFIRMED,
    ),
    EventType.STATUS_CHANGED: NotificationRule(email=True, template=_T.VERIFICATION_STATUS_CHANGE),
    EventType.AGENTS_ASSIGNED: NotificationRule(email=True, template=_T.VERIFICATION_AGENTS_ASSIGNED),
    EventType.EVIDENCE_ADDED: NotificationRule(in_app=True),
    # The two §7.6.2 milestones that exist only to be told on WhatsApp (D66). No in-app
    # entry and no email: the customer already has a status-change notification for the
    # same moment, and a second one would be noise rather than news.
    EventType.VERIFICATION_STARTED: NotificationRule(
        in_app=False, email=False,
        whatsapp=True, whatsapp_template=_T.WHATSAPP_VERIFICATION_STARTED,
    ),
    EventType.INSPECTION_COMPLETE: NotificationRule(
        in_app=False, email=False,
        whatsapp=True, whatsapp_template=_T.WHATSAPP_INSPECTION_COMPLETE,
    ),
    # §7.6.2 report delivery (WA-35): WhatsApp respects the opt-in, **email is
    # unconditional**. The durable record of a delivered report cannot depend on a
    # messaging preference, so `email=True` here is a requirement, not a default.
    EventType.REPORT_READY: NotificationRule(
        email=True, sms=True, template=_T.VERIFICATION_REPORT_READY,
        whatsapp=True, whatsapp_template=_T.WHATSAPP_REPORT_READY,
    ),
    EventType.REPORT_VERSIONED: NotificationRule(email=True, template=_T.VERIFICATION_REPORT_READY),
    EventType.SLA_BREACHED: NotificationRule(email=True, sms=True, template=_T.VERIFICATION_SLA_BREACH),
    EventType.REFUND_INITIATED: NotificationRule(in_app=True),
    EventType.RECHECK_DECISION: NotificationRule(email=True, template=_T.VERIFICATION_RECHECK_DECISION),
    # Agent
    EventType.NEW_JOB: NotificationRule(email=True, sms=True, template=_T.VERIFICATION_JOB_ALERT),
    EventType.TASK_REASSIGNED: NotificationRule(in_app=True),
    EventType.TASK_REJECTED: NotificationRule(email=True, template=_T.VERIFICATION_REVISION_REQUEST),
    EventType.PAYOUT_APPROVED: NotificationRule(email=True, template=_T.VERIFICATION_PAYOUT_APPROVED),
    EventType.PAYOUT_HELD: NotificationRule(email=True, template=_T.VERIFICATION_PAYOUT_HELD),
    # Positive-movement earnings alert (§15.1): in-app only, no external template.
    EventType.COMMISSION_CLEARED: NotificationRule(in_app=True),
    # Referral credit cleared to the referrer's balance (§17.1): in-app only.
    EventType.REFERRAL_CREDIT_EARNED: NotificationRule(in_app=True),
    # Abandoned-draft recovery (§17.1): one email, no in-app entry (it's a re-engagement nudge).
    EventType.ABANDONMENT_RECOVERY: NotificationRule(
        in_app=False, email=True, template=_T.VERIFICATION_ABANDONMENT_RECOVERY
    ),
    # Admin broadcast to an audience (§18.1): in-app + email, per-recipient (S22).
    EventType.BROADCAST_ANNOUNCEMENT: NotificationRule(email=True, template=_T.ADMIN_BROADCAST),
    # Admin
    EventType.CONFLICT_FLAGGED: NotificationRule(in_app=True),
    EventType.AGENT_NO_SHOW: NotificationRule(in_app=True),
    EventType.FRAUD_FLAGGED_MESSAGE: NotificationRule(in_app=True),
    # §7.6.5: in-app only, and deliberately so. The customer has already been answered
    # with the handover copy, so this is an operational signal — emailing it would page
    # the team for something the conversation has already recovered from.
    EventType.BOT_PIPELINE_FAILED: NotificationRule(in_app=True),
    EventType.DISPUTE_OPENED: NotificationRule(email=True, template=_T.VERIFICATION_DISPUTE_FILED),
    EventType.DISPUTE_RESOLVED: NotificationRule(email=True, template=_T.VERIFICATION_DISPUTE_RESOLVED),
    EventType.PAYMENT_SETTLED: NotificationRule(in_app=True),
    # Chat routing (§12.3): a routine message bumps the Chat counter only — never a notification.
    EventType.MESSAGE_SENT: NotificationRule(in_app=False, chat_only=True),
    # Compliance (§19): NDPA erasure decision to the data subject — in-app only, no external template.
    EventType.ERASURE_STATUS_CHANGED: NotificationRule(in_app=True),
    # Admin user management (§4.2): a suspended user cannot log in, so email is the only
    # channel that reaches them; the in-app entry still lands for post-reactivation review.
    EventType.ACCOUNT_SUSPENDED: NotificationRule(email=True, template=_T.ACCOUNT_DEACTIVATION),
    EventType.ACCOUNT_REACTIVATED: NotificationRule(email=True, template=_T.ACCOUNT_ACTIVATION),
    # §7.4.5 (D77): a delegate opted out in chat. In-app only — the buyer needs to know
    # their case has no delegate any more, not to be emailed about someone else's
    # messaging preference.
    EventType.DELEGATE_REVOKED: NotificationRule(in_app=True),
}

# Fallback for any event not explicitly listed — in-app only, no external fan-out.
_DEFAULT_RULE = NotificationRule(in_app=True)


def rule_for(event_type: EventType) -> NotificationRule:
    return RULES.get(event_type, _DEFAULT_RULE)

"""Notification event definitions — title/body templates and default channels."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from main.app.domain.notification.models import NotificationEvent


@dataclass
class EventSpec:
    title_tpl: str
    body_tpl: str
    # recipient_role is informational — the caller decides the recipient_id
    recipient_role: str = "customer"


_SPECS: dict[NotificationEvent, EventSpec] = {
    NotificationEvent.STATUS_CHANGE: EventSpec(
        title_tpl="Verification status updated",
        body_tpl="Your verification is now {to_state}.",
        recipient_role="customer",
    ),
    NotificationEvent.PAYMENT_CONFIRMED: EventSpec(
        title_tpl="Payment confirmed",
        body_tpl="Your payment was confirmed. Agents are being assigned.",
        recipient_role="customer",
    ),
    NotificationEvent.AGENTS_ASSIGNED: EventSpec(
        title_tpl="Agents assigned",
        body_tpl="Field agents have been assigned to your verification.",
        recipient_role="customer",
    ),
    NotificationEvent.JOB_ALERT: EventSpec(
        title_tpl="New job available",
        body_tpl="A new verification task is available for your role.",
        recipient_role="agent",
    ),
    NotificationEvent.REPORT_READY: EventSpec(
        title_tpl="Verification report ready",
        body_tpl="Your verification report is ready to view.",
        recipient_role="customer",
    ),
    NotificationEvent.NEW_MESSAGE: EventSpec(
        title_tpl="New message",
        body_tpl="You have a new message: {preview}",
        recipient_role="customer",
    ),
    NotificationEvent.FRAUD_FLAGGED_MESSAGE: EventSpec(
        title_tpl="Held message pending review",
        body_tpl="A message has been held for fraud review.",
        recipient_role="admin",
    ),
    NotificationEvent.REVISION_REQUEST: EventSpec(
        title_tpl="Revision requested",
        body_tpl="Admin has requested a revision for your task submission.",
        recipient_role="agent",
    ),
    NotificationEvent.SLA_BREACH: EventSpec(
        title_tpl="SLA breach alert",
        body_tpl="A verification has breached its SLA target.",
        recipient_role="admin",
    ),
    NotificationEvent.RECHECK_DECISION: EventSpec(
        title_tpl="Re-check request decision",
        body_tpl="Your re-check request has been {decision}.",
        recipient_role="customer",
    ),
    NotificationEvent.DISPUTE_FILED: EventSpec(
        title_tpl="Dispute filed",
        body_tpl="A dispute has been filed for verification {vid}.",
        recipient_role="admin",
    ),
    NotificationEvent.DISPUTE_RESOLVED: EventSpec(
        title_tpl="Dispute resolved",
        body_tpl="Your dispute has been resolved: {outcome}.",
        recipient_role="customer",
    ),
    NotificationEvent.PAYOUT_APPROVED: EventSpec(
        title_tpl="Payout approved",
        body_tpl="Your withdrawal request has been approved.",
        recipient_role="agent",
    ),
    NotificationEvent.PAYOUT_HELD: EventSpec(
        title_tpl="Payout on hold",
        body_tpl="Your withdrawal request is on hold: {reason}.",
        recipient_role="agent",
    ),
}


def get_spec(event: NotificationEvent) -> EventSpec:
    return _SPECS[event]


def render_title(event: NotificationEvent, context: dict) -> str:
    return _SPECS[event].title_tpl.format_map(_SafeFormatDict(context))


def render_body(event: NotificationEvent, context: dict) -> str:
    return _SPECS[event].body_tpl.format_map(_SafeFormatDict(context))


class _SafeFormatDict(dict):
    def __missing__(self, key: str) -> str:
        return f"{{{key}}}"

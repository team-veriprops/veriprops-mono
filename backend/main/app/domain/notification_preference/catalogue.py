"""What a user may switch off, and how it is described to them (PRD §12.4).

Derived from the §4.8 rule table rather than kept beside it: an event is configurable when
one of its external channels (email, SMS) is optional — used by the rule and not required.
Each configurable event carries the copy the preferences page shows and the audiences it is
addressed to, so a customer is never offered an agent's payout emails. A test keeps
`PREFERENCE_COPY` and the rule table in step.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Dict, FrozenSet, Iterable, List, Optional, Set, Tuple

from main.app.core.events.events import EventType
from main.app.domain.notification.rules import NotificationRule
from main.app.domain.user.auth.session.models import UserPersona, UserType


class ChannelMode(str, enum.Enum):
    """How one external channel behaves for one event."""

    UNUSED = "UNUSED"      # the event never goes out on this channel
    REQUIRED = "REQUIRED"  # always sent; not the user's to switch off
    OPTIONAL = "OPTIONAL"  # sent unless the user opted out


class PreferenceAudience(str, enum.Enum):
    """Who an event is addressed to."""

    CUSTOMER = "CUSTOMER"
    AGENT = "AGENT"
    ADMIN = "ADMIN"


@dataclass(frozen=True)
class PreferenceCopy:
    label: str
    description: str
    audiences: FrozenSet[PreferenceAudience]


_CUSTOMER = frozenset({PreferenceAudience.CUSTOMER})
_AGENT = frozenset({PreferenceAudience.AGENT})

# Listed in the order the preferences page shows them.
PREFERENCE_COPY: Dict[EventType, PreferenceCopy] = {
    EventType.PAYMENT_CONFIRMED: PreferenceCopy("Payment confirmed", "When your payment is received.", _CUSTOMER),
    EventType.AGENTS_ASSIGNED: PreferenceCopy("Agents assigned", "When our agents start work on your property.", _CUSTOMER),
    EventType.STATUS_CHANGED: PreferenceCopy("Status updates", "When your verification moves to its next stage.", _CUSTOMER),
    EventType.REPORT_READY: PreferenceCopy(
        "Report ready", "When your report is available. The email always comes; you can turn off the text.", _CUSTOMER,
    ),
    EventType.REPORT_VERSIONED: PreferenceCopy("Report updated", "When a new version of your report is released.", _CUSTOMER),
    EventType.RECHECK_DECISION: PreferenceCopy("Re-check decisions", "When we decide on a re-check you asked for.", _CUSTOMER),
    EventType.DISPUTE_OPENED: PreferenceCopy("Dispute opened", "When we receive a dispute you raised.", _CUSTOMER),
    EventType.DISPUTE_RESOLVED: PreferenceCopy("Dispute resolved", "When we decide on a dispute you raised.", _CUSTOMER),
    EventType.SLA_BREACHED: PreferenceCopy(
        "Delays", "If a verification runs past its target date.",
        frozenset({PreferenceAudience.CUSTOMER, PreferenceAudience.ADMIN}),
    ),
    EventType.ABANDONMENT_RECOVERY: PreferenceCopy(
        "Unfinished verifications", "A reminder about a verification you started but didn't pay for.", _CUSTOMER,
    ),
    EventType.NEW_JOB: PreferenceCopy("New jobs", "When a task is available for you.", _AGENT),
    EventType.TASK_REJECTED: PreferenceCopy("Revision requests", "When an admin asks you to revise a submission.", _AGENT),
    EventType.PAYOUT_APPROVED: PreferenceCopy("Payout approved", "When Finance approves a payout you requested.", _AGENT),
    EventType.PAYOUT_HELD: PreferenceCopy("Payout on hold", "When Finance holds a payout for review.", _AGENT),
    EventType.PAYOUT_PAID: PreferenceCopy("Payout sent", "When a payout reaches your bank.", _AGENT),
    EventType.PAYOUT_REJECTED: PreferenceCopy("Payout rejected", "When Finance rejects a payout.", _AGENT),
    EventType.BROADCAST_ANNOUNCEMENT: PreferenceCopy(
        "Announcements", "Service notices from the Veriprops team.", frozenset(PreferenceAudience),
    ),
}


def channel_modes(rule: NotificationRule) -> Tuple[ChannelMode, ChannelMode]:
    """(email, SMS) modes of one rule. A rule without a template sends neither."""
    if not rule.template or rule.chat_only:
        return ChannelMode.UNUSED, ChannelMode.UNUSED
    if not rule.email:
        email = ChannelMode.UNUSED
    else:
        email = ChannelMode.REQUIRED if rule.required_email else ChannelMode.OPTIONAL
    sms = ChannelMode.OPTIONAL if rule.sms else ChannelMode.UNUSED
    return email, sms


def is_configurable(rule: NotificationRule) -> bool:
    return ChannelMode.OPTIONAL in channel_modes(rule)


def audiences_for(user_type: Optional[str], personas: Iterable[str]) -> Set[PreferenceAudience]:
    """The audiences a user belongs to, from their account type and personas."""
    if (user_type or "").upper() == UserType.ADMIN.value:
        return {PreferenceAudience.ADMIN}
    held = set(personas or ())
    audiences = set()
    if UserPersona.CUSTOMER.value in held:
        audiences.add(PreferenceAudience.CUSTOMER)
    if UserPersona.AGENT.value in held:
        audiences.add(PreferenceAudience.AGENT)
    return audiences


def configurable_events(audiences: Set[PreferenceAudience]) -> List[EventType]:
    """The events a user in *audiences* may change, in page order."""
    return [event for event, copy in PREFERENCE_COPY.items() if copy.audiences & audiences]

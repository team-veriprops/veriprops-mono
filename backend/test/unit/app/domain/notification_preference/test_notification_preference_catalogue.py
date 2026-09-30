"""The notification-preference catalogue (§12.4) is derived from the §4.8 rule table.

What a user may switch off is decided here, never by the page that shows it: an event is
listed when one of its external channels is optional, each channel says whether it is
unused, required or optional, and a user is only shown the events addressed to them.
"""
import pytest

from main.app.core.events.events import EventType
from main.app.domain.notification.rules import RULES
from main.app.domain.notification_preference.catalogue import (
    PREFERENCE_COPY,
    ChannelMode,
    PreferenceAudience,
    audiences_for,
    channel_modes,
    configurable_events,
    is_configurable,
)
from main.app.domain.user.auth.session.models import UserPersona, UserType


def test_every_event_with_an_optional_channel_has_copy_and_nothing_else_does():
    configurable = {event for event, rule in RULES.items() if is_configurable(rule)}
    assert set(PREFERENCE_COPY) == configurable


def test_every_entry_names_who_receives_it():
    for event, copy in PREFERENCE_COPY.items():
        assert copy.label and copy.description, event
        assert copy.audiences, event


@pytest.mark.parametrize("event, email, sms", [
    (EventType.PAYMENT_CONFIRMED, ChannelMode.OPTIONAL, ChannelMode.OPTIONAL),
    (EventType.STATUS_CHANGED, ChannelMode.OPTIONAL, ChannelMode.UNUSED),
    (EventType.REPORT_READY, ChannelMode.REQUIRED, ChannelMode.OPTIONAL),
])
def test_each_channel_says_whether_it_is_unused_required_or_optional(event, email, sms):
    assert channel_modes(RULES[event]) == (email, sms)


def test_an_event_whose_only_channel_is_required_is_not_listed():
    for event in (EventType.ACCOUNT_SUSPENDED, EventType.ACCOUNT_REACTIVATED):
        assert channel_modes(RULES[event]) == (ChannelMode.REQUIRED, ChannelMode.UNUSED)
        assert event not in PREFERENCE_COPY


def test_in_app_only_and_chat_only_events_are_not_listed():
    assert EventType.MESSAGE_SENT not in PREFERENCE_COPY
    assert EventType.CASE_ON_HOLD not in PREFERENCE_COPY


class TestAudiences:
    def test_a_customer_sees_customer_events_and_broadcasts_but_not_agent_ones(self):
        events = configurable_events(audiences_for(UserType.USER.value, [UserPersona.CUSTOMER.value]))
        assert EventType.PAYMENT_CONFIRMED in events and EventType.BROADCAST_ANNOUNCEMENT in events
        assert EventType.NEW_JOB not in events and EventType.PAYOUT_PAID not in events

    def test_an_agent_sees_jobs_and_payouts_but_not_customer_payments(self):
        events = configurable_events(audiences_for(UserType.USER.value, [UserPersona.AGENT.value]))
        assert EventType.NEW_JOB in events and EventType.PAYOUT_PAID in events
        assert EventType.PAYMENT_CONFIRMED not in events

    def test_a_user_with_both_hats_sees_both(self):
        events = configurable_events(audiences_for(
            UserType.USER.value, [UserPersona.CUSTOMER.value, UserPersona.AGENT.value],
        ))
        assert EventType.PAYMENT_CONFIRMED in events and EventType.NEW_JOB in events

    def test_an_admin_sees_the_breaches_they_are_told_about(self):
        audiences = audiences_for(UserType.ADMIN.value, [])
        assert audiences == {PreferenceAudience.ADMIN}
        events = configurable_events(audiences)
        assert EventType.SLA_BREACHED in events and EventType.PAYMENT_CONFIRMED not in events

"""The two tables the channel is held to: §7.3.2 stages and the §7.3.4 matrix.

Both are places where the PRD states something and the code has to keep agreeing with it
as the rest of the system moves. A new `VerificationStatus` that nobody projects, or a
handoff row with no link to hand off with, are silent gaps — these tests make them loud.
"""
from __future__ import annotations

import pytest

from main.app.core.state.status import TaskState, VerificationStatus
from main.app.domain.channel.whatsapp.bot.capabilities import (
    ChannelAction,
    ChannelCapability,
    capability_for,
    handoff_intent_for,
)
from main.app.domain.channel.whatsapp.bot.projection import ChannelState, channel_state
from main.app.domain.channel.whatsapp.handoff.models import HandoffIntent


# ─── §7.3.2 projection ────────────────────────────────────────────

def test_a_conversation_with_no_case_is_an_enquiry():
    """Where every WhatsApp customer starts, and the one stage with no row to read."""
    assert channel_state(None) == ChannelState.ENQUIRY


@pytest.mark.parametrize("status", list(VerificationStatus), ids=lambda s: s.value)
def test_every_verification_status_projects_to_a_stage(status):
    """A status with no projection would raise mid-conversation, on a customer's status
    question — the worst possible place to discover it."""
    assert channel_state(status) in set(ChannelState)


@pytest.mark.parametrize(
    "status, expected",
    [
        (VerificationStatus.DRAFT, ChannelState.INTAKE_IN_PROGRESS),
        (VerificationStatus.SUBMITTED, ChannelState.INTAKE_COMPLETE),
        (VerificationStatus.PAYMENT_PENDING, ChannelState.PAYMENT_PENDING),
        (VerificationStatus.PAID, ChannelState.PAID),
        (VerificationStatus.IN_PROGRESS, ChannelState.VERIFYING),
        (VerificationStatus.UNDER_REVIEW, ChannelState.REPORT_READY),
        (VerificationStatus.COMPLETED, ChannelState.DELIVERED),
        # A dispute is a post-delivery conversation: the report exists and the customer
        # has it; what is open is whether it was right.
        (VerificationStatus.DISPUTED, ChannelState.DELIVERED),
        (VerificationStatus.CANCELLED, ChannelState.CLOSED),
        (VerificationStatus.REFUNDED, ChannelState.CLOSED),
        (VerificationStatus.FAILED, ChannelState.CLOSED),
    ],
    ids=lambda v: getattr(v, "value", v),
)
def test_status_projects_to_the_prd_stage(status, expected):
    assert channel_state(status) == expected


@pytest.mark.parametrize(
    "task_state, expected",
    [
        (TaskState.ACCEPTED, ChannelState.FIELD_INSPECTION),
        (TaskState.IN_PROGRESS, ChannelState.FIELD_INSPECTION),
        (TaskState.SUBMITTED, ChannelState.FIELD_INSPECTION),
        (TaskState.APPROVED, ChannelState.FIELD_INSPECTION),
        # Assigned is not started. Telling a customer their inspection is happening when
        # nobody has left yet is the small overstatement that costs trust later.
        (TaskState.ASSIGNED, ChannelState.VERIFYING),
        (TaskState.PENDING, ChannelState.VERIFYING),
        (None, ChannelState.VERIFYING),
    ],
    ids=lambda v: getattr(v, "value", str(v)),
)
def test_the_field_task_is_what_separates_verifying_from_inspection(task_state, expected):
    assert channel_state(VerificationStatus.IN_PROGRESS, task_state) == expected


def test_the_field_task_cannot_override_a_later_stage():
    """A completed case with an approved field task is delivered, not mid-inspection."""
    assert (
        channel_state(VerificationStatus.COMPLETED, TaskState.APPROVED)
        == ChannelState.DELIVERED
    )


# ─── §7.3.4 capability matrix ─────────────────────────────────────

@pytest.mark.parametrize(
    "action, expected",
    [
        (ChannelAction.LEARN, ChannelCapability.FULL),
        (ChannelAction.START_INTAKE, ChannelCapability.FULL),
        (ChannelAction.CHECK_STATUS, ChannelCapability.FULL),
        (ChannelAction.TALK_TO_HUMAN, ChannelCapability.FULL),
        # Money, canonical documents and reports live behind the address bar.
        (ChannelAction.PAY, ChannelCapability.HANDOFF),
        (ChannelAction.UPLOAD_DOCUMENTS, ChannelCapability.HANDOFF),
        (ChannelAction.VIEW_REPORT, ChannelCapability.HANDOFF),
        (ChannelAction.MANAGE_ACCOUNT, ChannelCapability.NOT_OFFERED),
    ],
    ids=lambda v: getattr(v, "value", v),
)
def test_the_matrix_matches_the_prd(action, expected):
    assert capability_for(action) == expected


@pytest.mark.parametrize("action", list(ChannelAction), ids=lambda a: a.value)
def test_every_action_has_a_verdict(action):
    assert capability_for(action) in set(ChannelCapability)


@pytest.mark.parametrize(
    "action", [a for a in ChannelAction if capability_for(a) == ChannelCapability.HANDOFF],
    ids=lambda a: a.value,
)
def test_every_handoff_action_has_a_link_to_hand_off_with(action):
    """A `HANDOFF` row with no §7.5 intent would have the bot announce a link it cannot
    mint — the customer waits for a message that never comes."""
    assert handoff_intent_for(action) in set(HandoffIntent)


@pytest.mark.parametrize(
    "action",
    [a for a in ChannelAction if capability_for(a) != ChannelCapability.HANDOFF],
    ids=lambda a: a.value,
)
def test_asking_a_non_handoff_action_for_a_link_is_a_bug(action):
    with pytest.raises(ValueError):
        handoff_intent_for(action)


def test_payment_is_never_something_the_bot_completes():
    """Decision A, restated as a test because it is the channel's whole anti-fraud
    posture: if payment were ever `FULL`, the payment pledge would become a lie."""
    assert capability_for(ChannelAction.PAY) == ChannelCapability.HANDOFF
    assert handoff_intent_for(ChannelAction.PAY) == HandoffIntent.PAY

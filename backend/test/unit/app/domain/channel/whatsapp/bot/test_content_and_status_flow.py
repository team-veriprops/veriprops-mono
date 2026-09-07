"""The words the bot says, and how the status flow branches (§26.6.1, §26.6.2, D54).

Copy is normally not worth testing. Three pieces of it here are, because they are
*obligations* rather than wording: the bot disclosure (§26.1.4), the payment pledge
(§26.1.1), and the rule that pricing comes from the live config and never from a literal
(D54). Each would be trivially easy to lose in an innocuous copy edit, and none would fail
anything else.

The status branching is tested here too because it is pure — the engine fetches, the flow
decides — so the "customer with three cases" behaviour can be pinned without a database.
"""
from __future__ import annotations

from datetime import date

import pytest

from main.app.core.state.status import VerificationTier
from main.app.domain.channel.whatsapp.bot import content
from main.app.domain.channel.whatsapp.bot.flows import status as status_flow
from main.app.domain.channel.whatsapp.bot.projection import ChannelState
from main.app.domain.channel.whatsapp.bot.session.models import EscalationReason
from main.app.domain.channel.whatsapp.bot.support_hours import Coverage, CoverageState
from main.app.domain.verification.pricing_config.models import (
    PricingTierDto,
    TierPricingViewDto,
)


# ─── Obligations ──────────────────────────────────────────────────

def test_the_welcome_discloses_the_bot_and_states_the_payment_pledge():
    """§26.1.4 and §26.1.1. Both ride on the welcome, which is the only message every
    customer is guaranteed to receive."""
    message = content.welcome()

    assert "automated assistant" in message
    assert content.PAYMENT_PLEDGE in message
    assert "veriprops.ng" in message


def test_the_welcome_offers_the_menu_so_the_numbers_mean_something():
    message = content.welcome()

    for item in content.MENU_ITEMS:
        assert item in message


def test_pricing_is_rendered_from_the_live_config():
    """D54 — the admin pricing screen is the single source of truth. A bot quoting a
    hardcoded figure is a trust problem, not a copy problem."""
    view = TierPricingViewDto(
        tiers=[
            PricingTierDto(tier=VerificationTier.PREMIUM, price_ngn_minor=25_000_00),
            PricingTierDto(tier=VerificationTier.BASIC, price_ngn_minor=5_000_00),
            PricingTierDto(tier=VerificationTier.STANDARD, price_ngn_minor=12_500_00),
        ]
    )

    message = content.pricing(view)

    assert "₦5,000" in message
    assert "₦12,500" in message
    assert "₦25,000" in message
    # Cheapest first: the customer is deciding, not being upsold.
    assert message.index("₦5,000") < message.index("₦12,500") < message.index("₦25,000")
    assert content.PAYMENT_PLEDGE in message


def test_pricing_with_no_configured_tiers_offers_a_person_rather_than_a_number():
    """The one thing worse than not knowing the price is inventing one."""
    message = content.pricing(TierPricingViewDto(tiers=[]))

    assert "₦" not in message
    assert "team member" in message


@pytest.mark.parametrize("reason", list(EscalationReason), ids=lambda r: r.value)
def test_every_escalation_reason_has_copy(reason):
    """A reason with no copy would raise inside the handover — the bot going silent at
    precisely the moment §26.6.5 says it must not."""
    message = content.escalation(reason, Coverage(CoverageState.OPEN, 12))

    assert message.strip()


def test_escalation_says_someone_is_joining_inside_hours():
    message = content.escalation(
        EscalationReason.EXPLICIT_REQUEST, Coverage(CoverageState.OPEN, 12)
    )

    assert "joining this chat now" in message


def test_escalation_states_a_window_outside_hours():
    """An unstaffed "joining now" reads as a lie the moment nobody joins."""
    message = content.escalation(
        EscalationReason.EXPLICIT_REQUEST, Coverage(CoverageState.CLOSED, 12)
    )

    assert "12 hours" in message
    assert "joining this chat now" not in message


@pytest.mark.parametrize(
    "question, expected",
    [
        ("How does it work?", content.FaqTopic.HOW_IT_WORKS),
        ("what do i get in the report", content.FaqTopic.WHAT_YOU_GET),
        ("how long does it take", content.FaqTopic.HOW_LONG),
        ("what do you check exactly", content.FaqTopic.WHAT_WE_CHECK),
        ("is my data safe with you", content.FaqTopic.IS_MY_DATA_SAFE),
    ],
)
def test_the_faq_answers_what_it_covers(question, expected):
    assert content.faq_topic_for(question) == expected


@pytest.mark.parametrize(
    "question",
    [
        "what's the weather like",
        "do you have an office in Abuja",
        "who founded veriprops",
        "",
    ],
)
def test_the_faq_says_nothing_outside_its_content_set(question):
    """§26.6.2 — there is deliberately no nearest-match fallback. A confident answer to a
    question we do not cover is worse than a handover."""
    assert content.faq_topic_for(question) is None


@pytest.mark.parametrize("topic", list(content.FaqTopic), ids=lambda t: t.value)
def test_every_declared_faq_topic_has_an_answer(topic):
    assert content.faq_answer(topic).strip()


# ─── Status flow ──────────────────────────────────────────────────

def _case(vid: str, label: str = "12 Ademola Street, Ikeja, Lagos") -> status_flow.CaseSummary:
    return status_flow.CaseSummary(
        vid=vid,
        property_label=label,
        status_label="Verification in progress",
        channel_state=ChannelState.VERIFYING,
        sla_due_date=date(2026, 9, 15),
    )


def test_no_cases_offers_to_start_one():
    outcome = status_flow.render([])

    assert not outcome.awaits_choice
    assert "start a verification" in outcome.text


def test_one_case_is_answered_outright():
    outcome = status_flow.render([_case("VP-2026-0001")])

    assert not outcome.awaits_choice
    assert "VP-2026-0001" in outcome.text
    assert "Verification in progress" in outcome.text
    assert "15 Sep 2026" in outcome.text
    # The full picture stays behind the login (§26.3.4).
    assert "veriprops.ng" in outcome.text


def test_several_cases_ask_rather_than_guess():
    """An answer about the wrong property is worse than a question."""
    cases = [_case("VP-2026-0001", "Ikeja"), _case("VP-2026-0002", "Lekki")]

    outcome = status_flow.render(cases)

    assert outcome.awaits_choice
    assert outcome.offered_vids == ("VP-2026-0001", "VP-2026-0002")
    assert "1. Ikeja" in outcome.text
    assert "2. Lekki" in outcome.text


@pytest.mark.parametrize(
    "answer, expected",
    [
        ("1", "VP-2026-0001"),
        ("2", "VP-2026-0002"),
        ("VP-2026-0002", "VP-2026-0002"),
        ("vp-2026-0001", "VP-2026-0001"),
        (" 2 ", "VP-2026-0002"),
    ],
)
def test_a_choice_can_be_a_position_or_a_reference(answer, expected):
    """Both are on screen in the message being replied to, so both are what real people
    type."""
    cases = [_case("VP-2026-0001"), _case("VP-2026-0002")]

    selected = status_flow.resolve_choice(cases, answer)

    assert selected is not None and selected.vid == expected


@pytest.mark.parametrize(
    "answer",
    ["0", "3", "-1", "", "   ", "VP-9999-9999", "actually how much does it cost"],
)
def test_a_non_choice_is_not_forced_into_one(answer):
    """`None` means the customer moved on, and the engine classifies fresh. A flow that
    insisted would trap someone who changed their mind."""
    cases = [_case("VP-2026-0001"), _case("VP-2026-0002")]

    assert status_flow.resolve_choice(cases, answer) is None


def test_a_stray_number_in_a_sentence_cannot_select_a_case():
    cases = [_case("VP-2026-0001"), _case("VP-2026-0002")]

    assert status_flow.render_choice(cases, "2 bedrooms please") is None

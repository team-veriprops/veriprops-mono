"""The chat intake flow (PRD §5.1, §26.3.4, D69/D70).

Four questions, and the bar for them is set by the **website**, not by this file:
`canAdvanceSubmissionStep` lets a web customer past the property step with a type and
either an address or a landmark, then a tier. So chat parity is exactly that, plus the
state (the web gets it from address autocomplete, which a chat has no equivalent of).

What is being defended here is that the collected answers come out in the *wizard's own
shape*. The handoff seeds a real draft and hands into the existing submission wizard, so a
key renamed here silently produces an empty wizard on the other side — a customer who
answered four questions and sees a blank form is the worst outcome this flow has.
"""
from __future__ import annotations

import pytest

from main.app.core.state.status import VerificationTier
from main.app.domain.channel.whatsapp.bot.flows import intake
from main.app.domain.property.models import PropertyType
from main.app.domain.verification.pricing_config.models import (
    PricingTierDto,
    TierPricingViewDto,
)

TIERS = TierPricingViewDto(
    tiers=[
        PricingTierDto(tier=VerificationTier.BASIC, price_ngn_minor=59_999_00),
        PricingTierDto(tier=VerificationTier.STANDARD, price_ngn_minor=120_000_00),
        PricingTierDto(tier=VerificationTier.PREMIUM, price_ngn_minor=300_000_00),
    ]
)


def _run(answers: list[str]) -> intake.IntakeOutcome:
    """Drive the flow through a list of replies, as the engine would."""
    outcome = intake.begin()
    for answer in answers:
        outcome = intake.answer(outcome.step, answer, outcome.collected, TIERS)
    return outcome


# ─── The happy path ───────────────────────────────────────────────

def test_the_flow_opens_by_asking_what_kind_of_property():
    outcome = intake.begin()

    assert outcome.step == intake.IntakeStep.PROPERTY_TYPE
    assert "land" in outcome.text.lower()
    assert not outcome.complete


def test_four_answers_complete_the_intake():
    outcome = _run(["1", "12 Ademola Street, Ikeja", "Lagos", "2"])

    assert outcome.complete
    assert outcome.step == intake.IntakeStep.DONE


def test_the_collected_payload_is_the_wizard_shape():
    """The seeded draft is read by the web wizard, so these keys are a wire contract —
    camelCase, and exactly the names `SubmissionState` declares."""
    outcome = _run(["1", "12 Ademola Street, Ikeja", "Lagos", "2"])

    payload = outcome.collected
    assert payload["property"]["propertyType"] == PropertyType.LAND.value
    assert payload["property"]["address"] == "12 Ademola Street, Ikeja"
    assert payload["property"]["state"] == "Lagos"
    assert payload["tier"] == VerificationTier.STANDARD.value
    # The wizard reads these even when empty; a missing key is a crash, not a blank field.
    assert payload["property"]["landmark"] == ""
    assert payload["property"]["details"] == {}
    # Consent is never collected in chat — §5.3's bundled acceptance happens on the web.
    assert payload["consentAccepted"] is False


@pytest.mark.parametrize(
    "answer, expected",
    [
        ("1", PropertyType.LAND.value),
        ("2", PropertyType.BUILDING.value),
        ("land", PropertyType.LAND.value),
        ("Building", PropertyType.BUILDING.value),
        ("a house", PropertyType.BUILDING.value),
        ("bare land", PropertyType.LAND.value),
    ],
)
def test_property_type_accepts_a_number_or_the_word(answer, expected):
    """The prompt offers numbers, but people answer in words — both are what a real
    customer types, so both are accepted rather than one being 'wrong'."""
    outcome = intake.answer(intake.IntakeStep.PROPERTY_TYPE, answer, {}, TIERS)

    assert outcome.collected["property"]["propertyType"] == expected


@pytest.mark.parametrize(
    "answer, expected",
    [("1", "BASIC"), ("2", "STANDARD"), ("3", "PREMIUM"), ("premium", "PREMIUM"), ("Basic", "BASIC")],
)
def test_tier_accepts_a_number_or_the_name(answer, expected):
    collected = _run(["1", "12 Ademola Street", "Lagos"]).collected

    outcome = intake.answer(intake.IntakeStep.TIER, answer, collected, TIERS)

    assert outcome.collected["tier"] == expected


def test_the_tier_prompt_quotes_live_prices():
    """D54 again — a tier the customer picks by price must be priced from the config."""
    outcome = _run(["1", "12 Ademola Street", "Lagos"])

    assert "₦59,999" in outcome.text
    assert "₦300,000" in outcome.text


# ─── What the customer actually types ─────────────────────────────

@pytest.mark.parametrize("answer", ["", "   ", "yes", "asdf", "7"])
def test_an_unusable_property_type_re_asks_rather_than_guessing(answer):
    """Guessing LAND for an unclear answer would put the wrong property type on the case,
    and the customer would never be shown it again."""
    outcome = intake.answer(intake.IntakeStep.PROPERTY_TYPE, answer, {}, TIERS)

    assert outcome.step == intake.IntakeStep.PROPERTY_TYPE
    assert not outcome.complete
    assert outcome.reprompted


@pytest.mark.parametrize("answer", ["", "   "])
def test_an_empty_location_re_asks(answer):
    collected = intake.answer(intake.IntakeStep.PROPERTY_TYPE, "1", {}, TIERS).collected

    outcome = intake.answer(intake.IntakeStep.LOCATION, answer, collected, TIERS)

    assert outcome.step == intake.IntakeStep.LOCATION
    assert outcome.reprompted


def test_a_description_with_no_street_is_kept_as_a_landmark():
    """§5.1 1C's escape valve: plenty of Nigerian plots have no formatted address, and the
    web wizard accepts either. Refusing this answer would strand exactly those customers."""
    collected = intake.answer(intake.IntakeStep.PROPERTY_TYPE, "1", {}, TIERS).collected

    outcome = intake.answer(
        intake.IntakeStep.LOCATION, "behind the old GT Bank in Ikeja", collected, TIERS
    )

    prop = outcome.collected["property"]
    assert prop["landmark"] == "behind the old GT Bank in Ikeja"
    assert prop["address"] == ""


def test_an_address_with_a_street_number_is_kept_as_an_address():
    collected = intake.answer(intake.IntakeStep.PROPERTY_TYPE, "1", {}, TIERS).collected

    outcome = intake.answer(
        intake.IntakeStep.LOCATION, "12 Ademola Street, Ikeja", collected, TIERS
    )

    assert outcome.collected["property"]["address"] == "12 Ademola Street, Ikeja"
    assert outcome.collected["property"]["landmark"] == ""


@pytest.mark.parametrize("answer", ["Lagos", "lagos state", "  Ogun  "])
def test_state_is_taken_as_typed(answer):
    """No server-side state list exists, and the wizard validates on the web — so the chat
    records what the customer said rather than refusing a spelling it doesn't recognise."""
    collected = _run(["1", "12 Ademola Street"]).collected

    outcome = intake.answer(intake.IntakeStep.STATE, answer, collected, TIERS)

    assert outcome.collected["property"]["state"] == answer.strip()


@pytest.mark.parametrize("answer", ["", "  "])
def test_an_empty_state_re_asks(answer):
    collected = _run(["1", "12 Ademola Street"]).collected

    outcome = intake.answer(intake.IntakeStep.STATE, answer, collected, TIERS)

    assert outcome.step == intake.IntakeStep.STATE
    assert outcome.reprompted


def test_an_unusable_tier_re_asks_and_shows_the_prices_again():
    collected = _run(["1", "12 Ademola Street", "Lagos"]).collected

    outcome = intake.answer(intake.IntakeStep.TIER, "the cheap one please", collected, TIERS)

    assert outcome.step == intake.IntakeStep.TIER
    assert outcome.reprompted
    assert "₦59,999" in outcome.text


def test_answers_already_given_survive_a_reprompt():
    """A customer who fumbles the tier must not lose the address they already typed."""
    collected = _run(["1", "12 Ademola Street", "Lagos"]).collected

    outcome = intake.answer(intake.IntakeStep.TIER, "???", collected, TIERS)

    assert outcome.collected["property"]["address"] == "12 Ademola Street"
    assert outcome.collected["property"]["state"] == "Lagos"


def test_the_closing_message_carries_the_payment_pledge():
    """§26.1.1 — the handoff to the website is the single most impersonation-prone moment in
    the whole channel, so the pledge is repeated exactly there."""
    outcome = _run(["1", "12 Ademola Street", "Lagos", "2"])

    assert "veriprops.ng" in outcome.text

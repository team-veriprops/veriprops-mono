"""Chat intake (PRD §5.1, §26.3.4, D69/D70).

Four questions, and the bar is the **website's**: `canAdvanceSubmissionStep` lets a web
customer past the property step with a type and either an address or a landmark, then a
tier. Chat asks exactly that, plus the state — which the web gets free from address
autocomplete and a chat has no equivalent for. §5.1's conditional facts are left to the
wizard, where the customer will see them on a real form (D70).

Two properties make this flow safe to hand off:

* **The collected payload is the wizard's own shape** — camelCase, the keys
  `SubmissionState` declares. Completion seeds a real draft with it and hands into the
  existing submission wizard (D69), so a renamed key here shows up as an empty form in
  front of a customer who just answered four questions.
* **Nothing is guessed.** An answer the flow cannot read re-asks rather than defaulting.
  A wrong property type is not something the customer will ever be shown again, so a
  cheerful guess is worse than another question.

Pure, like every module in this package: the engine owns the session and the I/O.
"""
from __future__ import annotations

import enum
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

from main.app.core.state.status import VerificationTier
from main.app.domain.property.models import PropertyType
from main.app.domain.verification.pricing_config.models import TierPricingViewDto


class IntakeStep(int, enum.Enum):
    """Where the conversation is. Stored on the session as `step`."""

    PROPERTY_TYPE = 0
    LOCATION = 1
    STATE = 2
    TIER = 3
    DONE = 4


@dataclass(frozen=True)
class IntakeOutcome:
    """What to say, where the flow now is, and what has been gathered so far."""

    text: str
    step: IntakeStep
    collected: Dict[str, Any]
    complete: bool = False
    # True when the step did not advance because the answer was unusable. The engine reads
    # it to keep a re-ask out of the §26.6.2 unmatched counter — a customer mistyping inside
    # a flow the bot is running has not "not been understood", they have been asked again.
    reprompted: bool = False


# What a customer types when they mean each property type. Numbers because the prompt
# offers them; words because people answer in words regardless.
_PROPERTY_TYPE_WORDS = [
    (PropertyType.BUILDING, ("2", "building", "house", "flat", "apartment", "duplex", "bungalow")),
    (PropertyType.LAND, ("1", "land", "plot", "acre", "hectare", "bare land")),
]

_TIER_WORDS = [
    (VerificationTier.BASIC, ("1", "basic")),
    (VerificationTier.STANDARD, ("2", "standard")),
    (VerificationTier.PREMIUM, ("3", "premium")),
]

# A location that opens with a house number, or names a street-like word, is an address;
# anything else is §5.1 1C's landmark escape valve. Deliberately generous toward
# "landmark": plenty of Nigerian plots have no formatted address, and the web wizard
# accepts either, so the only wrong answer here is refusing the customer's description.
_ADDRESS_SHAPE = re.compile(
    r"^\d+[\s,]|\b(street|str|road|rd|avenue|ave|close|crescent|drive|lane|way|estate|plaza)\b",
    re.IGNORECASE,
)


def begin() -> IntakeOutcome:
    """Open the flow with the first question."""
    return IntakeOutcome(text=_ask_property_type(), step=IntakeStep.PROPERTY_TYPE, collected=_blank())


def answer(
    step: IntakeStep, text: str, collected: Dict[str, Any], tiers: TierPricingViewDto
) -> IntakeOutcome:
    """Apply one reply and produce the next question — or the closing message."""
    payload = _with_defaults(collected)
    said = (text or "").strip()

    if step == IntakeStep.PROPERTY_TYPE:
        chosen = _match(said, _PROPERTY_TYPE_WORDS)
        if not chosen:
            return _reprompt(_ask_property_type(), IntakeStep.PROPERTY_TYPE, payload)
        payload["property"]["propertyType"] = chosen.value
        return IntakeOutcome(_ask_location(chosen), IntakeStep.LOCATION, payload)

    if step == IntakeStep.LOCATION:
        if not said:
            return _reprompt(_ask_location(_property_type_of(payload)), IntakeStep.LOCATION, payload)
        if _ADDRESS_SHAPE.search(said):
            payload["property"]["address"] = said
        else:
            payload["property"]["landmark"] = said
        return IntakeOutcome(_ask_state(), IntakeStep.STATE, payload)

    if step == IntakeStep.STATE:
        if not said:
            return _reprompt(_ask_state(), IntakeStep.STATE, payload)
        payload["property"]["state"] = said
        return IntakeOutcome(_ask_tier(tiers), IntakeStep.TIER, payload)

    if step == IntakeStep.TIER:
        chosen = _match(said, _TIER_WORDS)
        if not chosen:
            return _reprompt(_ask_tier(tiers), IntakeStep.TIER, payload)
        payload["tier"] = chosen.value
        return IntakeOutcome(_closing(), IntakeStep.DONE, payload, complete=True)

    return IntakeOutcome(_closing(), IntakeStep.DONE, payload, complete=True)


# ─── Shape ────────────────────────────────────────────────────────

def _blank() -> Dict[str, Any]:
    """`SubmissionState`'s own shape, with every key the wizard reads.

    Present-but-empty rather than absent: the wizard reads these fields directly, and a
    missing key is a crash where an empty string is just a blank input.
    """
    return {
        "property": {
            "propertyType": PropertyType.LAND.value,
            "address": "",
            "landmark": "",
            "state": "",
            "details": {},
        },
        "tier": VerificationTier.STANDARD.value,
        "currency": "NGN",
        # §5.3's bundled acceptance is an evidentiary record with an IP and a version.
        # A chat message is not that, so consent is always taken on the web.
        "consentAccepted": False,
    }


def _with_defaults(collected: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """A working copy that always has the full shape, however little has been gathered."""
    payload = _blank()
    if not collected:
        return payload
    payload.update({k: v for k, v in collected.items() if k != "property"})
    payload["property"] = {**payload["property"], **(collected.get("property") or {})}
    return payload


def _property_type_of(payload: Dict[str, Any]) -> PropertyType:
    return PropertyType(payload["property"]["propertyType"])


def _match(said: str, table):
    """First entry whose words appear in the answer. Ordered most-specific-first."""
    lowered = said.lower()
    if not lowered:
        return None
    for value, words in table:
        if any(word == lowered or word in lowered.split() or word in lowered for word in words):
            return value
    return None


def _reprompt(text: str, step: IntakeStep, payload: Dict[str, Any]) -> IntakeOutcome:
    return IntakeOutcome(text, step, payload, reprompted=True)


# ─── Copy ─────────────────────────────────────────────────────────

def _ask_property_type() -> str:
    return (
        "Let's get your verification started. 🏡\n\n"
        "First — what are you verifying?\n\n"
        "1. Land / a plot\n"
        "2. A building\n\n"
        "Reply with the number, or just tell me."
    )


def _ask_location(kind: PropertyType) -> str:
    noun = "building" if kind == PropertyType.BUILDING else "land"
    return (
        f"Where is the {noun}?\n\n"
        "An address is ideal — but a description works too, like "
        "\"behind the old GT Bank in Ikeja\"."
    )


def _ask_state() -> str:
    return "Which state is it in?"


def _ask_tier(tiers: TierPricingViewDto) -> str:
    from main.app.domain.channel.whatsapp.bot import content

    if not tiers.tiers:
        return "Which level of check would you like — Basic, Standard, or Premium?"
    lines = [
        f"{position}. {tier.tier.value.capitalize()} — {content.naira(tier.price_ngn_minor)}"
        for position, tier in enumerate(
            sorted(tiers.tiers, key=lambda t: t.price_ngn_minor), start=1
        )
    ]
    body = "\n".join(lines)
    return f"Which level of check would you like?\n\n{body}\n\nReply with the number."


def _closing() -> str:
    """The handoff message.

    The §26.1.1 pledge is repeated here rather than assumed from the welcome: this is the
    moment a customer is asked to leave WhatsApp and pay, which is the single most
    impersonation-prone step in the channel.
    """
    from main.app.domain.channel.whatsapp.bot import content

    return (
        "Got everything I need. 👍\n\n"
        "Here's your secure link to confirm the details and pay:\n"
        "{link}\n\n"
        f"⚠️ {content.PAYMENT_PLEDGE}\n\n"
        "The link works once and expires in 15 minutes — say \"pay\" and I'll send a fresh one."
    )

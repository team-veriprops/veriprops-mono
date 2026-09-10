"""Intent-classification vocabulary (PRD §26.6, D44/D48/D53).

The intent set is **closed**. A classifier may only answer with a member of ``BotIntent``,
and anything it returns that is not one becomes ``UNKNOWN`` — which routes to a human.
That is the guarantee §26.6.4 rests on: the bot never guesses, so the worst a confused or
compromised model can do is hand the conversation to a person.

The enum covers more than the classifier produces. ``STOP_MESSAGES``/``START_MESSAGES``
are matched as keywords before the classifier ever runs (D64), and ``CONTINUE_CASE`` is
usually recognised by the shape of a VID rather than by a model. They live here anyway
because the bot engine dispatches on one vocabulary, whatever recognised the turn.
"""
from __future__ import annotations

import enum
from typing import Optional

from main.appodus_utils import Object
from main.appodus_utils.config.settings import IntentProvider


class BotIntent(str, enum.Enum):
    """What a customer's message is asking for (§26.6.2 flows + §26.6.4 guardrails)."""

    MENU = "MENU"                                # greeting / "help" / "options"
    LEARN = "LEARN"                              # how Verify works
    PRICING = "PRICING"                          # what it costs
    START_VERIFICATION = "START_VERIFICATION"    # begin intake
    CHECK_STATUS = "CHECK_STATUS"                # where is my verification
    CONTINUE_CASE = "CONTINUE_CASE"              # "Continue verification VP-…" (§26.4.3)
    # The two §26.3.4 `HANDOFF` actions a customer *asks* for. Uploading is the third, but
    # it is recognised by a document arriving (§26.6.3) rather than by words, so it needs no
    # intent of its own.
    PAY = "PAY"                                  # "how do I pay?" → a §26.5 pay link
    VIEW_REPORT = "VIEW_REPORT"                  # "send me my report" → a §26.5 report link
    LINK_ACCOUNT = "LINK_ACCOUNT"                # connect this number to an account
    TALK_TO_HUMAN = "TALK_TO_HUMAN"              # explicit escalation request
    REFUND_OR_CANCELLATION = "REFUND_OR_CANCELLATION"  # always human (§26.6.2)
    STOP_MESSAGES = "STOP_MESSAGES"              # opt out of everything (D64)
    START_MESSAGES = "START_MESSAGES"            # opt back into utility updates (D64)
    # §26.6.4 — a request for a verification judgment, legal opinion, Trust Score reading,
    # or property-specific assessment. Recognised so it can be *refused*, never answered.
    JUDGMENT_REQUEST = "JUDGMENT_REQUEST"
    # Out of scope, or recognised with too little confidence to act on. Routes to a human.
    UNKNOWN = "UNKNOWN"


# The subset a live classifier is allowed to choose from. The keyword-only members are
# excluded so a model cannot revoke someone's consent or claim a case by inference —
# those turns must come from the customer's own literal words.
CLASSIFIABLE_INTENTS: frozenset[BotIntent] = frozenset(
    {
        BotIntent.MENU,
        BotIntent.LEARN,
        BotIntent.PRICING,
        BotIntent.START_VERIFICATION,
        BotIntent.CHECK_STATUS,
        # Safe for a model to choose: neither revokes consent nor claims a case. Both are
        # answered by a link the engine mints from a case *it* resolved for an account it
        # verified, so the worst a misclassification costs is an unwanted offer to pay.
        BotIntent.PAY,
        BotIntent.VIEW_REPORT,
        BotIntent.LINK_ACCOUNT,
        BotIntent.TALK_TO_HUMAN,
        BotIntent.REFUND_OR_CANCELLATION,
        BotIntent.JUDGMENT_REQUEST,
        BotIntent.UNKNOWN,
    }
)


class IntentResult(Object):
    """One classification outcome.

    ``confidence`` is the classifier's own 0–1 self-report, compared against
    ``INTENT_MIN_CONFIDENCE`` by the caller. ``provider`` records which backend answered,
    so the §26.10 escalation-rate metric can tell a coverage gap from an outage.
    """

    intent: BotIntent
    confidence: float = 1.0
    provider: Optional[IntentProvider] = None

    @classmethod
    def unknown(cls, provider: Optional[IntentProvider] = None) -> "IntentResult":
        """The safe answer. Every failure path returns this rather than raising."""
        return cls(intent=BotIntent.UNKNOWN, confidence=0.0, provider=provider)


def coerce_intent(raw: object) -> BotIntent:
    """Read a classifier's answer as a closed-set member, or ``UNKNOWN``.

    A model asked for one of eleven strings can still return a twelfth. This is the one
    place that possibility is handled, so no caller has to remember it.
    """
    if isinstance(raw, BotIntent):
        return raw if raw in CLASSIFIABLE_INTENTS else BotIntent.UNKNOWN
    try:
        intent = BotIntent(str(raw).strip().upper())
    except ValueError:
        return BotIntent.UNKNOWN
    return intent if intent in CLASSIFIABLE_INTENTS else BotIntent.UNKNOWN

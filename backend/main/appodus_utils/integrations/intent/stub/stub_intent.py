"""Deterministic intent classifier — the default in local/test/dev (D43/D53).

A keyword table, in the same spirit as the OTP and WhatsApp determinism contracts: the
guardrail suite and the e2e conversation scripts must give the same answer every run, and
a live model cannot promise that. `ENVIRONMENT=test` pins the provider here, so no
automated run ever calls a model.

It is a stand-in, not a mock. The scoring rules that matter downstream are real:
a matched phrase yields a confident answer, an unmatched message yields ``UNKNOWN`` at
zero confidence, and a message that matches two intents yields the more specific one —
so a test that drives the low-confidence branch drives the same branch the live adapter
would.
"""
from __future__ import annotations

import re
from typing import List, Tuple

from kink import inject

from main.appodus_utils.config.settings import IntentProvider
from main.appodus_utils.integrations.intent.interface import IIntentClassifier
from main.appodus_utils.integrations.intent.models import BotIntent, IntentResult

# Confidence a keyword hit reports. High enough to clear any sane
# INTENT_MIN_CONFIDENCE, and not 1.0 — nothing about a keyword match is certain.
_MATCH_CONFIDENCE = 0.9

# Ordered most-specific-first: the first table entry whose pattern matches wins, so
# "how much does a refund cost" reads as a refund question rather than a pricing one.
# Patterns are matched against the lowercased message with word boundaries, so "prices"
# matches and "enterprises" does not.
_KEYWORD_TABLE: List[Tuple[BotIntent, List[str]]] = [
    # Guardrail topics first — §26.6.4 says these route to a human with no partial answer,
    # so nothing further down the table may claim them.
    (
        BotIntent.JUDGMENT_REQUEST,
        [
            r"is (this|the|that) (property|land|house|title|document|deed)",
            r"(is|are) (it|they|this|that) (legit|genuine|real|fake|safe|authentic)",
            r"should i (buy|pay|proceed|go ahead|trust)",
            r"legal (advice|opinion|view)",
            r"what does (my|the) trust score mean",
            r"(interpret|explain) (my|the) trust score",
            r"do you think",
            # The verdict vocabulary itself, wherever it appears. Deliberately broad: a
            # false positive costs a warm handover to a person, while a false negative
            # is the bot answering "is this genuine?" — the one thing §26.1.3 forbids.
            r"(genuine|legit|authentic|fake|fraudulent|forged)",
            r"a scam",
        ],
    ),
    (
        BotIntent.REFUND_OR_CANCELLATION,
        [r"refund", r"cancel(l)?(ation)?", r"money back", r"charge ?back"],
    ),
    (
        BotIntent.TALK_TO_HUMAN,
        [
            r"talk to (a )?(human|person|someone|agent|staff)",
            r"speak (to|with) (a )?(human|person|someone|agent)",
            r"customer (care|service|support)",
            r"real person",
            r"human",
        ],
    ),
    (
        BotIntent.LINK_ACCOUNT,
        [r"link (my )?(account|number)", r"connect (my )?(account|number)", r"verify my number"],
    ),
    (
        BotIntent.CHECK_STATUS,
        [
            r"status",
            r"(how|what)('s| is)? .*(going|progress)",
            r"(is|any) .*(update|news)",
            r"where is my (verification|report|case)",
            r"track",
        ],
    ),
    # Pricing sits above intake on purpose: "how much does it cost to verify a property"
    # names both, and it is a question about money. A message that wants to *start* one
    # carries no cost word, so it falls through to the entry below.
    (
        BotIntent.PRICING,
        [r"pric(e|es|ing)", r"cost", r"how much", r"fee(s)?", r"charge(s)?", r"rate(s)?"],
    ),
    # The two §26.3.4 handoff asks. Both sit *below* the question each could be mistaken
    # for — "how much do I pay" is a pricing question and "where is my report" is a status
    # question, and neither wants a link — so every pattern here names an action rather
    # than just the noun.
    (
        BotIntent.PAY,
        [
            r"pay(ment)? link",
            r"(how|where) (do|can) i pay",
            r"(want|need|ready) to pay",
            r"make (a )?payment",
            r"pay now",
            r"^pay$",
            r"checkout",
        ],
    ),
    (
        BotIntent.VIEW_REPORT,
        [
            r"(send|share) (me )?(my |the )?report",
            r"(view|open|read|download|get|see) (my |the )?report",
            r"report link",
            r"copy of (my |the )?report",
            r"my report",
        ],
    ),
    (
        BotIntent.START_VERIFICATION,
        [
            r"start (a )?(verification|check)",
            r"verify (a |my |this )?(property|land|house|title)",
            r"new verification",
            r"begin",
            r"i want to (verify|check)",
        ],
    ),
    (
        BotIntent.LEARN,
        [
            r"how (does|do) (it|this|verify|you) work",
            r"what (is|do) (veriprops|you)",
            r"tell me (more|about)",
            r"learn",
            r"explain",
        ],
    ),
    (
        BotIntent.MENU,
        [r"^(hi|hello|hey|good (morning|afternoon|evening))\b", r"^menu$", r"^help$", r"options"],
    ),
]

_COMPILED: List[Tuple[BotIntent, List[re.Pattern[str]]]] = [
    (intent, [re.compile(rf"\b(?:{p})", re.IGNORECASE) for p in patterns])
    for intent, patterns in _KEYWORD_TABLE
]


@inject
class StubIntentClassifier(IIntentClassifier):
    """Keyword-table classifier. Never touches the network."""

    @property
    def platform(self) -> IntentProvider:
        return IntentProvider.STUB

    async def classify(self, text: str) -> IntentResult:
        message = (text or "").strip().lower()
        if not message:
            return IntentResult.unknown(self.platform)

        for intent, patterns in _COMPILED:
            if any(pattern.search(message) for pattern in patterns):
                return IntentResult(
                    intent=intent, confidence=_MATCH_CONFIDENCE, provider=self.platform
                )

        return IntentResult.unknown(self.platform)

"""Hard constraints on what the bot may answer (PRD §7.1.3, §7.6.4, WA-03/WA-39).

These are **deterministic and sit outside the classifier** (D44). A model decides which
flow a message belongs to; it does not decide whether a message is allowed to reach a
flow. That ordering is the whole guarantee: a classifier that is wrong, slow, jailbroken,
or replaced by a different vendor cannot make the bot render a verification judgment,
because the check that forbids it never consults the classifier.

Three things are checked, in the order a message meets them:

1. **Language** (Decision L) — English only at v1; anything else gets a polite English
   reply and a human.
2. **Guarded topics** (§7.6.4) — verification judgments, legal opinions, Trust Score
   readings, property-specific assessments, pricing negotiation, refund decisions, and
   requests for promises about outcomes or timelines. No partial answers: the whole turn
   routes to a person.
3. **The classified intent** — the two intents that are recognisable but never
   answerable (`JUDGMENT_REQUEST`, `REFUND_OR_CANCELLATION`).

A guardrail hit is not an error. It is the bot working: the customer gets a warm reply
and a person, which §7.1.3 says is the only place judgments come from.
"""
from __future__ import annotations

import re
from typing import NamedTuple, Optional

from main.app.domain.channel.whatsapp.bot.session.models import EscalationReason
from main.appodus_utils.integrations.intent.models import BotIntent


class GuardrailVerdict(NamedTuple):
    """Why a turn may not be answered by the bot, if it may not be."""

    reason: EscalationReason


# §7.6.4 topic patterns. Deliberately broader than the intent classifier's: this list
# exists to catch what the classifier missed, so overlap is the design, not duplication.
# A false positive costs a handover to a person; a false negative is the bot giving a
# verdict on someone's property, which is the failure the Trust Charter is built around.
_GUARDED_TOPIC_PATTERNS = [
    # Verdicts on a specific thing
    r"\b(is|are)\s+(it|this|that|they|the)\b.{0,40}\b(genuine|legit|authentic|fake|valid|"
    r"real|safe|clean|fraudulent|forged|a scam)\b",
    r"\b(should|shall)\s+i\b.{0,30}\b(buy|pay|proceed|continue|trust|sign|invest)\b",
    r"\bdo you (think|believe|reckon)\b",
    r"\b(is|are)\s+(this|that|the)\s+(seller|agent|owner|landlord|document|title|deed|"
    r"survey|property|land|house)\b",
    # The verdict vocabulary on its own, in any word order. "is this genuine" and "tell
    # me if this land is genuine" are the same question, and only the first is a question
    # shape — so the noun-phrase patterns above cannot be the only net.
    r"\b(genuine|legit|authentic|fake|fraudulent|forged)\b",
    r"\ba scam\b",
    # Legal opinion
    r"\blegal (advice|opinion|view|position)\b",
    r"\b(can|should) i sue\b",
    r"\bis (this|that) (legal|lawful|illegal)\b",
    # Trust Score interpretation
    r"\btrust score\b.{0,30}\b(mean|means|meaning|good|bad|enough|interpret)\b",
    r"\b(what|how) (does|do|should) .{0,20}\btrust score\b",
    # Pricing negotiation
    # `negotiat\w*` rather than `negotiat`: a trailing `\b` after a prefix never matches
    # the word it is a prefix of, which is the classic way a pattern list quietly does
    # nothing.
    r"\b(discount|cheaper|reduce the price|negotiat\w*|bargain|best price|lower the (price|fee))\b",
    r"\bcan you do it for\b",
    # Refund / money decisions
    r"\b(refund|money back|charge ?back|reverse the payment)\b",
    r"\bcancel(l)?(ation)? (my|the|this)\b",
    # Promises beyond published SLAs
    r"\b(guarantee|promise|assure me|are you sure it will)\b",
    r"\bexactly when will\b",
]

_COMPILED_TOPICS = [re.compile(p, re.IGNORECASE) for p in _GUARDED_TOPIC_PATTERNS]

# Intents that are recognisable but never answerable by the bot.
_INTENT_ESCALATIONS = {
    BotIntent.JUDGMENT_REQUEST: EscalationReason.GUARDRAIL_TOPIC,
    BotIntent.REFUND_OR_CANCELLATION: EscalationReason.REFUND_OR_CANCELLATION,
    BotIntent.TALK_TO_HUMAN: EscalationReason.EXPLICIT_REQUEST,
}

# Characters outside Latin-1 that mark a script we do not serve at v1. Latin letters with
# accents are *not* enough on their own — a Nigerian name or a French loanword is not a
# French message — so the non-Latin test below is about script, and the word test that
# follows is about vocabulary.
_NON_LATIN = re.compile(r"[Ѐ-ӿ؀-ۿऀ-ॿ一-鿿぀-ヿ]")

# High-frequency function words from the languages most likely to reach a Nigerian
# business line. Function words rather than nouns: they are what a real sentence in that
# language cannot avoid, and what an English sentence almost never contains.
_NON_ENGLISH_MARKERS = re.compile(
    r"\b(bonjour|merci|s'il vous pla[iî]t|je (suis|voudrais|veux)|nous|vous|"
    r"hola|gracias|por favor|quiero|buenos d[ií]as|"
    r"guten tag|danke|bitte|ich (bin|m[oö]chte)|"
    r"ol[aá]|obrigad[oa]|quero)\b",
    re.IGNORECASE,
)


def is_non_english(text: str) -> bool:
    """Whether a message is plainly not English (Decision L).

    Deliberately conservative. Nigerian English carries Yoruba, Igbo and Hausa words and
    plenty of Pidgin, all written in Latin script — treating those as foreign would
    escalate a large share of ordinary customers. So only a non-Latin script or explicit
    foreign function words trip this; everything else is given to the bot, which will
    route it to a human anyway if it cannot understand it.
    """
    message = (text or "").strip()
    if not message:
        return False
    return bool(_NON_LATIN.search(message) or _NON_ENGLISH_MARKERS.search(message))


def check_message(text: str) -> Optional[GuardrailVerdict]:
    """Guardrails that read the customer's own words, before any classification."""
    message = (text or "").strip()
    if not message:
        return None
    if is_non_english(message):
        return GuardrailVerdict(EscalationReason.NON_ENGLISH)
    if any(pattern.search(message) for pattern in _COMPILED_TOPICS):
        return GuardrailVerdict(EscalationReason.GUARDRAIL_TOPIC)
    return None


def check_intent(intent: BotIntent) -> Optional[GuardrailVerdict]:
    """Guardrails that read the classified intent.

    Runs after ``check_message`` and catches what phrasing did not: a customer who asks
    "what's your view on the survey plan I sent" trips no pattern but classifies as a
    judgment request.
    """
    reason = _INTENT_ESCALATIONS.get(intent)
    return GuardrailVerdict(reason) if reason else None

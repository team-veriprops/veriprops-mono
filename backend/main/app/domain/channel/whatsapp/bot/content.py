"""Everything the bot says (PRD §7.6, D54).

Code-owned on purpose. The alternative — a `whatsapp_content_entries` table with an admin
editor — would create a second source of pricing truth, and a stale row would have the bot
quoting a price the website does not charge. So prose lives here, where it is reviewed
like code, and **every number comes from the live config** rather than from the prose.

Three pieces of copy are not decoration and must not be edited away:

* the **bot disclosure** (§7.1.4) — the customer is told they are talking to automation;
* the **payment pledge** (§7.1.1) — "payments only ever happen at veriprops.ng", repeated
  in the welcome and in every payment handoff, which is the whole anti-impersonation
  posture in one sentence;
* the **content-set boundary** (§7.6.2) — the FAQ answers only what it covers. There is
  no fallback paragraph that improvises; an unanswered question routes to a person.
"""
from __future__ import annotations

import enum
from typing import Optional

from main.app.config.settings import settings
from main.app.core.state.status import VerificationTier
from main.app.domain.channel.whatsapp.bot.session.models import EscalationReason
from main.app.domain.channel.whatsapp.bot.support_hours import Coverage
from main.app.domain.verification.pricing_config.models import TierPricingViewDto

# §7.1.1 — stated in the welcome, repeated in every payment handoff, published on the site.
PAYMENT_PLEDGE = (
    "Payments only ever happen at veriprops.ng — check the address bar before you pay."
)

# §7.1.4 — the bot says what it is, unprompted, on first contact.
BOT_DISCLOSURE = (
    "I'm {brand}' automated assistant — I can bring in a human anytime you want one."
)

MENU_ITEMS = [
    "1. Learn how Verify works",
    "2. Start a verification",
    "3. Check my status",
    "4. Talk to a human",
    "5. Pricing",
]


class FaqTopic(str, enum.Enum):
    """The maintained content set (§7.6.2). What is not here is not answered."""

    HOW_IT_WORKS = "HOW_IT_WORKS"
    WHAT_YOU_GET = "WHAT_YOU_GET"
    HOW_LONG = "HOW_LONG"
    WHAT_WE_CHECK = "WHAT_WE_CHECK"
    IS_MY_DATA_SAFE = "IS_MY_DATA_SAFE"


_FAQ_ANSWERS: dict[FaqTopic, str] = {
    FaqTopic.HOW_IT_WORKS: (
        "Here's how Verify works:\n\n"
        "1. You tell us about the property — location, type, and what documents you hold.\n"
        "2. You pay on veriprops.ng.\n"
        "3. Our verified agents do the work: registry search, a physical site visit, and "
        "a legal review on the higher tiers.\n"
        "4. You get a certified report in your portal, with everything they found.\n\n"
        "You can start right here in this chat — just say \"start a verification\"."
    ),
    FaqTopic.WHAT_YOU_GET: (
        "You get a certified report in your Veriprops portal: the registry findings, "
        "photos and GPS-stamped evidence from the site visit, a Trust Score, and — on "
        "Standard and Premium — a lawyer's review.\n\n"
        "The report lives in your account, so you can open it or share it whenever you "
        "need to."
    ),
    FaqTopic.HOW_LONG: (
        "Turnaround depends on the tier you choose, and you'll see the exact date on your "
        "dashboard as soon as payment is confirmed. We'll message you at each milestone "
        "if you opt in.\n\n"
        "If a specific deadline matters to you, say so and I'll bring in a team member."
    ),
    FaqTopic.WHAT_WE_CHECK: (
        "Depending on the tier: the land registry record, the physical site and its "
        "boundaries, the survey plan, and a legal review of the title documents.\n\n"
        "What we find goes in the report. I can't give a view on a specific property "
        "myself — that comes from our team and the certified report."
    ),
    FaqTopic.IS_MY_DATA_SAFE: (
        "Yes. Your documents and reports live in your Veriprops account behind your own "
        "login — never in this chat. Anything you send here is treated as unofficial, "
        "which is why we hand you a secure link when documents are involved.\n\n"
        f"{PAYMENT_PLEDGE}"
    ),
}

# Which question maps to which answer. Matched literally, before the classifier: the FAQ
# is the one place where covering *less* is the correct behaviour, so the match is
# phrase-based rather than inferred.
_FAQ_PATTERNS: list[tuple[FaqTopic, tuple[str, ...]]] = [
    (FaqTopic.HOW_IT_WORKS, ("how does it work", "how do you work", "how it works", "how does verify work")),
    (FaqTopic.WHAT_YOU_GET, ("what do i get", "what's in the report", "what is in the report", "sample report")),
    (FaqTopic.HOW_LONG, ("how long", "how many days", "turnaround", "when will it be ready")),
    (FaqTopic.WHAT_WE_CHECK, ("what do you check", "what do you verify", "what is checked", "what does it cover")),
    (FaqTopic.IS_MY_DATA_SAFE, ("is my data safe", "data safe", "privacy", "is it secure", "my documents safe")),
]


def brand() -> str:
    """The customer-facing name. `settings.BRAND` is a slug and reads as a typo in prose."""
    return settings.BRAND_DISPLAY_NAME


def welcome() -> str:
    """§7.6.1 — greeting, bot disclosure, payment pledge, and the five-item menu."""
    return (
        f"Hello 👋 Welcome to {brand()}.\n\n"
        f"{BOT_DISCLOSURE.format(brand=brand())}\n\n"
        f"⚠️ {PAYMENT_PLEDGE}\n\n"
        f"{menu()}"
    )


def menu() -> str:
    items = "\n".join(MENU_ITEMS)
    return f"What would you like to do?\n\n{items}\n\nJust reply with a number or tell me in your own words."


def faq_topic_for(text: str) -> Optional[FaqTopic]:
    """The content-set entry that answers *text*, or ``None``.

    ``None`` means "outside the content set", which §7.6.2 says routes to a human. There
    is deliberately no nearest-match fallback: a confident answer to a question we do not
    actually cover is worse than a handover.
    """
    message = (text or "").strip().lower()
    if not message:
        return None
    for topic, phrases in _FAQ_PATTERNS:
        if any(phrase in message for phrase in phrases):
            return topic
    return None


def faq_answer(topic: FaqTopic) -> str:
    return _FAQ_ANSWERS[topic]


def learn() -> str:
    """The general "tell me about Verify" answer — the content set's front door."""
    return _FAQ_ANSWERS[FaqTopic.HOW_IT_WORKS]


def pricing(view: TierPricingViewDto) -> str:
    """§7.6.2 pricing, rendered from the live admin config (D54).

    Never a hardcoded figure: the admin pricing screen is the single source of truth, and
    a bot quoting yesterday's price is a trust problem, not a copy problem.
    """
    if not view.tiers:
        return (
            "I can't pull up our current pricing right now — let me get a team member to "
            "confirm it for you."
        )
    lines = [
        f"• {_tier_label(tier.tier)} — {_naira(tier.price_ngn_minor)}"
        for tier in sorted(view.tiers, key=lambda t: t.price_ngn_minor)
    ]
    body = "\n".join(lines)
    return (
        f"Here's what a verification costs today:\n\n{body}\n\n"
        f"Prices are per property and include the full report.\n\n"
        f"⚠️ {PAYMENT_PLEDGE}"
    )


def _tier_label(tier: VerificationTier) -> str:
    return tier.value.capitalize()


def _naira(minor: int) -> str:
    """Kobo → a readable naira amount. Whole naira: we do not price in kobo."""
    return f"₦{minor // 100:,}"


# ─── Escalation, refusal and failure copy ─────────────────────────

def _coverage_line(coverage: Coverage) -> str:
    """§7.6.2 — "a team member is joining" inside hours, a stated window outside."""
    if coverage.is_open:
        return "A team member is joining this chat now."
    return (
        f"Our team is offline right now, but someone will reply here within "
        f"{coverage.response_hours} hours."
    )


_ESCALATION_OPENINGS: dict[EscalationReason, str] = {
    EscalationReason.EXPLICIT_REQUEST: "Of course — connecting you with someone.",
    EscalationReason.GUARDRAIL_TOPIC: (
        "That's a question for our team rather than for me. I don't give views on "
        "specific properties, documents or scores — those come from our verifiers and "
        "the certified report."
    ),
    EscalationReason.REFUND_OR_CANCELLATION: (
        "Anything to do with refunds or cancellations is handled by a person, not by me."
    ),
    EscalationReason.UNMATCHED_INTENTS: (
        "I'm not following, and I'd rather not guess — let me bring in a colleague."
    ),
    EscalationReason.NON_ENGLISH: (
        "Sorry — I can only understand English for now. A team member will pick this up."
    ),
    EscalationReason.CAPABILITY_NOT_OFFERED: (
        "I can't do that from WhatsApp, but a team member can help you with it."
    ),
    EscalationReason.UNSUPPORTED_MEDIA: (
        "Thanks for sending that. I can't read it myself, so I'm passing it to a "
        "team member."
    ),
    EscalationReason.PIPELINE_FAILURE: (
        "We're having a technical issue on our side — sorry about that."
    ),
}


def escalation(reason: EscalationReason, coverage: Coverage) -> str:
    """What the customer reads when a conversation goes to a person (§7.6.2)."""
    return f"{_ESCALATION_OPENINGS[reason]}\n\n{_coverage_line(coverage)}"


def failure_fallback(coverage: Coverage) -> str:
    """§7.6.5 — an outage must never look like a scam that stopped replying."""
    return escalation(EscalationReason.PIPELINE_FAILURE, coverage)


def account_management_not_offered() -> str:
    """§7.3.4 — account and settings are a website surface, not a chat one."""
    return (
        "Account settings live on veriprops.ng — sign in there and you'll find everything "
        "under your profile. I can help with verifications, status and pricing here."
    )


def unlinked_number() -> str:
    """§7.4.3 — the bot never reads case data to an unverified number.

    The refusal is warm and explains the next step, because the person on the other end
    is usually the customer on a second handset, not an attacker.
    """
    return (
        "I can't share verification details with a number that isn't linked to a "
        "Veriprops account yet — that's how we keep your case private.\n\n"
        "Say \"link my account\" and I'll send you a secure link to connect this number."
    )


def no_cases() -> str:
    return (
        "I can't find a verification on your account yet. If you'd like to start one, "
        "just say \"start a verification\"."
    )

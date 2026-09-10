"""Everything the bot says (PRD §26.6, D54).

Code-owned on purpose. The alternative — a `whatsapp_content_entries` table with an admin
editor — would create a second source of pricing truth, and a stale row would have the bot
quoting a price the website does not charge. So prose lives here, where it is reviewed
like code, and **every number comes from the live config** rather than from the prose.

Three pieces of copy are not decoration and must not be edited away:

* the **bot disclosure** (§26.1.4) — the customer is told they are talking to automation;
* the **payment pledge** (§26.1.1) — "payments only ever happen at veriprops.ng", repeated
  in the welcome and in every payment handoff, which is the whole anti-impersonation
  posture in one sentence;
* the **content-set boundary** (§26.6.2) — the FAQ answers only what it covers. There is
  no fallback paragraph that improvises; an unanswered question routes to a person.
"""
from __future__ import annotations

import enum
from typing import Optional

from main.app.config.settings import settings
from main.app.core.state.status import VerificationTier
from main.app.domain.channel.whatsapp.bot.capabilities import ChannelAction
from main.app.domain.channel.whatsapp.bot.session.models import EscalationReason
from main.app.domain.channel.whatsapp.bot.support_hours import Coverage
from main.app.domain.verification.pricing_config.models import TierPricingViewDto

# §26.1.1 — stated in the welcome, repeated in every payment handoff, published on the site.
PAYMENT_PLEDGE = (
    "Payments only ever happen at veriprops.ng — check the address bar before you pay."
)

# §26.1.4 — the bot says what it is, unprompted, on first contact.
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
    """The maintained content set (§26.6.2). What is not here is not answered."""

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
    """§26.6.1 — greeting, bot disclosure, payment pledge, and the five-item menu."""
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

    ``None`` means "outside the content set", which §26.6.2 says routes to a human. There
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
    """§26.6.2 pricing, rendered from the live admin config (D54).

    Never a hardcoded figure: the admin pricing screen is the single source of truth, and
    a bot quoting yesterday's price is a trust problem, not a copy problem.
    """
    if not view.tiers:
        return (
            "I can't pull up our current pricing right now — let me get a team member to "
            "confirm it for you."
        )
    lines = [
        f"• {_tier_label(tier.tier)} — {naira(tier.price_ngn_minor)}"
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


def naira(minor: int) -> str:
    """Kobo → a readable naira amount. Whole naira: we do not price in kobo.

    Public because the intake flow quotes tiers too, and two renderings of the same price
    is exactly the drift D54 exists to prevent.
    """
    return f"₦{minor // 100:,}"


# ─── Escalation, refusal and failure copy ─────────────────────────

def _coverage_line(coverage: Coverage) -> str:
    """§26.6.2 — "a team member is joining" inside hours, a stated window outside."""
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
    EscalationReason.VOICE_NOTE: (
        "Thanks for the voice note. I can't listen to recordings myself, so a team member "
        "will listen and reply here."
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
    """What the customer reads when a conversation goes to a person (§26.6.2)."""
    return f"{_ESCALATION_OPENINGS[reason]}\n\n{_coverage_line(coverage)}"


def failure_fallback(coverage: Coverage) -> str:
    """§26.6.5 — an outage must never look like a scam that stopped replying."""
    return escalation(EscalationReason.PIPELINE_FAILURE, coverage)


def account_management_not_offered() -> str:
    """§26.3.4 — account and settings are a website surface, not a chat one."""
    return (
        "Account settings live on veriprops.ng — sign in there and you'll find everything "
        "under your profile. I can help with verifications, status and pricing here."
    )


def unlinked_number() -> str:
    """§26.4.3 + §26.4.5 — the bot never reads case data to an unverified number.

    One message for both people who reach it, because the bot cannot tell them apart and
    must not guess: the customer on a second handset, and the third party asking about
    someone else's case ("my relative is handling it" — the social-engineering script
    §26.4.5 exists to defeat). Guessing wrong in either direction is bad. Sending the
    stranger down the linking flow wastes an OTP on an account that does not have this
    case on it; sending the customer down the delegate route tells them to ask permission
    for their own verification.

    So it states the refusal once and names **both** legitimate routes. Warm throughout,
    because most people asking are exactly who they say they are.
    """
    return (
        "I can't share verification details with a number that isn't linked to a "
        "Veriprops account yet — that's how we keep every case private, and we don't "
        "make exceptions.\n\n"
        "If the verification is yours, say \"link my account\" and I'll send you a secure "
        "link to connect this number.\n\n"
        "If it belongs to someone else, they can share updates with you, or authorize you "
        "as a delegate from the case page on veriprops.ng — then I can keep you posted on "
        "its progress."
    )


def no_cases() -> str:
    return (
        "I can't find a verification on your account yet. If you'd like to start one, "
        "just say \"start a verification\"."
    )



# ─── Messaging consent (§26.4.6, D64) ──────────────────────────────


def messages_stopped() -> str:
    """Confirms a STOP. Answered in one turn, by the bot, always.

    An opt-out is binding the moment it is typed, so it can never wait for a person to
    read it — and "I didn't understand" in reply to STOP is the single worst thing this
    channel could say. The confirmation also states the way back, because the common
    reason for a mistaken STOP is a fat-fingered menu reply.
    """
    return (
        "Done — I've stopped WhatsApp updates and offers to this number.\n\n"
        "You'll still get everything by email, and your verifications carry on exactly as "
        "before. Say \"START\" any time to switch progress updates back on."
    )


def messages_restarted() -> str:
    """Confirms a START, and is honest about what it does *not* restore.

    START brings back progress updates only. Marketing needs a deliberate opt-in on the
    web (D64), so saying so here is the difference between a customer who knows where the
    control is and one who thinks a word in chat re-consented them to everything.
    """
    return (
        "Progress updates are back on for this number.\n\n"
        "News and offers stay off — you can switch those on under WhatsApp in your "
        "account settings on veriprops.ng."
    )


def messages_stopped_unknown_number() -> str:
    """A STOP from a number we hold no consent for.

    There is nothing to revoke — we were not messaging them — but the reply still has to
    read as "yes, understood". Answering "I don't have you on file" would sound like a
    refusal to a person who just asked to be left alone.
    """
    return (
        "Understood — this number won't receive updates or offers from us.\n\n"
        "If you'd like help with a verification, just say hello and I'll take it from there."
    )


# ─── Non-text inbound (§26.6.3) ────────────────────────────────────

# §26.1.6/§26.6.1's evidence rule, in the customer's words. Repeated verbatim wherever a
# document arrives over chat, because the whole point is that it is the *same* promise
# every time: what lands in WhatsApp is not what the verifiers work from.
EVIDENCE_RULE = (
    "One thing to know: documents sent over WhatsApp don't go into your verification "
    "file — only uploads made on veriprops.ng do. That's what keeps the evidence trail "
    "clean."
)


def document_received_with_link(link: str) -> str:
    """§26.6.3 — a document arrived and we know which case it belongs to."""
    return (
        "Thanks for sending that.\n\n"
        f"{EVIDENCE_RULE}\n\n"
        "Here's a secure link to upload it properly:\n"
        f"{link}\n\n"
        f"⚠️ {PAYMENT_PLEDGE}"
    )


def document_received_unlinked() -> str:
    """§26.6.3 + §26.4.3 — a document from a number we cannot tie to an account.

    No upload link: an `upload` link authorizes writing to one specific case, so issuing
    one here would mean guessing whose case it is from a phone number alone.
    """
    return (
        "Thanks for sending that.\n\n"
        f"{EVIDENCE_RULE}\n\n"
        "Say \"link my account\" and I'll send you a secure link to connect this number — "
        "then I can point you straight at the right upload page."
    )


def document_received_no_case() -> str:
    """A linked customer with nothing open to attach the document to."""
    return (
        "Thanks for sending that.\n\n"
        f"{EVIDENCE_RULE}\n\n"
        "I can't see an open verification on your account to attach it to. Say "
        "\"start a verification\" and we'll get one going."
    )


def document_choose_case(prompt: str) -> str:
    """Several open cases — ask which before issuing a link scoped to exactly one."""
    return f"Thanks for sending that.\n\n{prompt}"


# ─── Pay and report handoffs (§26.3.4, §26.4.2) ─────────────────────


def pay_with_link(link: str) -> str:
    """§26.3.4 — the customer asked to pay, and we know which case they owe on.

    The §26.1.1 pledge is not optional here. This is the one message in the channel that
    sends a person to a payment page, so it is the exact message an impersonator would
    imitate — and the pledge is what lets the customer tell the two apart.
    """
    return (
        "Here's your secure payment link:\n"
        f"{link}\n\n"
        "It's good for 15 minutes and works once — just say \"pay\" if you need a fresh "
        "one.\n\n"
        f"⚠️ {PAYMENT_PLEDGE}"
    )


def pay_no_case() -> str:
    """A linked customer with nothing waiting to be paid for."""
    return (
        "I can't see a verification waiting for payment on your account.\n\n"
        "If you'd like to start one, just say \"start a verification\" and I'll take your "
        "details."
    )


def pay_choose_case(prompt: str) -> str:
    """Several unpaid cases — ask which before minting a link scoped to exactly one."""
    return f"Happy to help you pay.\n\n{prompt}"


def report_with_link(link: str) -> str:
    """§26.4.2 — the report link, minted on request.

    Carries no payment pledge: this link opens a report, and attaching a payment warning
    to it would teach customers that the two messages look the same.
    """
    return (
        "Here's a secure link to your report:\n"
        f"{link}\n\n"
        "It's good for 15 minutes and works once. You can also open it any time from your "
        "account on veriprops.ng."
    )


def report_no_case() -> str:
    """A linked customer whose report is not ready yet."""
    return (
        "You don't have a finished report waiting yet.\n\n"
        "Say \"status\" and I'll tell you exactly where your verification has got to and "
        "when to expect it."
    )


def report_choose_case(prompt: str) -> str:
    """Several finished cases — ask which report before minting a link for one."""
    return f"Happy to send that over.\n\n{prompt}"


def handoff_unlinked(action: ChannelAction) -> str:
    """A pay or report request from a number we cannot tie to an account (§26.4.3).

    One function rather than two messages: the refusal and the way out are identical, and
    only the opening clause differs. A handoff token names a customer *and* a case, so
    issuing one from a phone number alone would mean guessing whose money or whose report
    is being asked for — the same rule that governs the §26.6.3 document link.
    """
    opening = {
        ChannelAction.PAY: (
            "Before I can hand you a payment link, this number needs to be linked to "
            "your Veriprops account — that's how I know which verification you're paying "
            "for."
        ),
        ChannelAction.VIEW_REPORT: (
            "Before I can send a report, this number needs to be linked to your Veriprops "
            "account — reports only ever go to the person they belong to."
        ),
    }[action]
    return (
        f"{opening}\n\n"
        "Say \"link my account\" and I'll send you a secure link to connect it. It only "
        "takes a moment.\n\n"
        f"⚠️ {PAYMENT_PLEDGE}"
    )


def case_not_found() -> str:
    """A reference the customer quoted that is not one of theirs (§26.4.3, D58).

    Deliberately reads as "we can't find it on your account" rather than "that isn't
    yours": case references travel on receipts and reports, so confirming that one exists
    would make the reference space probeable from any WhatsApp number.
    """
    return (
        "I can't find that reference on your account. Double-check it and try again — "
        "or say \"status\" and I'll show you what you do have."
    )

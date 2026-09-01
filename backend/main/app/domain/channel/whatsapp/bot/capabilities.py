"""The §7.3.4 capability matrix, as data (WA-17).

§7.3.4 is a table in the PRD; this is the same table the code can be held to. It exists
so that "pay and report are website-only" is enforced by a lookup rather than by every
flow author remembering — a flow bug then produces a handoff or a refusal, never an
in-chat payment.

The three verdicts are meaningfully different:

* ``FULL`` — the bot does it in the conversation.
* ``HANDOFF`` — the customer finishes on veriprops.ng through a §7.5 single-use link.
  Money, canonical documents and reports live behind the address bar (Decisions A, B, M).
* ``NOT_OFFERED`` — WhatsApp is not a place to manage an account. Routed to a person or
  to the website, never attempted.
"""
from __future__ import annotations

import enum

from main.app.domain.channel.whatsapp.handoff.models import HandoffIntent


class ChannelAction(str, enum.Enum):
    """The rows of §7.3.4 — the things a customer can want to do."""

    LEARN = "LEARN"
    START_INTAKE = "START_INTAKE"
    UPLOAD_DOCUMENTS = "UPLOAD_DOCUMENTS"
    PAY = "PAY"
    CHECK_STATUS = "CHECK_STATUS"
    VIEW_REPORT = "VIEW_REPORT"
    TALK_TO_HUMAN = "TALK_TO_HUMAN"
    MANAGE_ACCOUNT = "MANAGE_ACCOUNT"


class ChannelCapability(str, enum.Enum):
    FULL = "FULL"
    HANDOFF = "HANDOFF"
    NOT_OFFERED = "NOT_OFFERED"


# The WhatsApp column of §7.3.4. The website column is `FULL` for every row except the
# two the matrix marks canonical, so it is not modelled here — this table exists to
# constrain the thin surface, not to describe the vault.
_WHATSAPP_CAPABILITIES: dict[ChannelAction, ChannelCapability] = {
    ChannelAction.LEARN: ChannelCapability.FULL,
    ChannelAction.START_INTAKE: ChannelCapability.FULL,
    ChannelAction.UPLOAD_DOCUMENTS: ChannelCapability.HANDOFF,
    ChannelAction.PAY: ChannelCapability.HANDOFF,
    ChannelAction.CHECK_STATUS: ChannelCapability.FULL,
    ChannelAction.VIEW_REPORT: ChannelCapability.HANDOFF,
    ChannelAction.TALK_TO_HUMAN: ChannelCapability.FULL,
    ChannelAction.MANAGE_ACCOUNT: ChannelCapability.NOT_OFFERED,
}

# Which §7.5 link a handoff action needs. Every `HANDOFF` row must appear here, or the
# bot would announce a handoff it has no way to perform.
_HANDOFF_INTENTS: dict[ChannelAction, HandoffIntent] = {
    ChannelAction.UPLOAD_DOCUMENTS: HandoffIntent.UPLOAD,
    ChannelAction.PAY: HandoffIntent.PAY,
    ChannelAction.VIEW_REPORT: HandoffIntent.REPORT,
}


def capability_for(action: ChannelAction) -> ChannelCapability:
    """What WhatsApp may do with *action* (§7.3.4)."""
    return _WHATSAPP_CAPABILITIES[action]


def handoff_intent_for(action: ChannelAction) -> HandoffIntent:
    """The §7.5 link a handoff action hands off with.

    Raises for an action that is not a handoff, because asking is then a bug in the
    caller — a `FULL` action has nothing to hand off and a `NOT_OFFERED` one has nowhere
    to hand off to.
    """
    if capability_for(action) != ChannelCapability.HANDOFF:
        raise ValueError(f"{action.value} is not a handoff action on WhatsApp (§7.3.4).")
    return _HANDOFF_INTENTS[action]

"""The §26.3.4 capability matrix, as data (WA-17).

§26.3.4 is a table in the PRD; this is the same table the code can be held to. It exists
so that "pay and report happen behind the address bar" is enforced by a lookup rather than
by every flow author remembering — a flow bug then produces a handoff or a refusal, never an
in-chat payment. The assistant answers in the same terms on every surface: in the portal a
handoff is a direct link to the page, on WhatsApp a §26.5 single-use link to it.

The three verdicts are meaningfully different:

* ``FULL`` — the bot does it in the conversation.
* ``HANDOFF`` — the customer finishes on veriprops.ng, through the link their surface gives.
  Money, canonical documents and reports live behind the address bar (Decisions A, B, M).
* ``NOT_OFFERED`` — WhatsApp is not a place to manage an account. Routed to a person or
  to the website, never attempted.
"""
from __future__ import annotations

import enum


class ChannelAction(str, enum.Enum):
    """The rows of §26.3.4 — the things a customer can want to do."""

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


# What the assistant may do with each row of §26.3.4 — WhatsApp's column, which the portal
# assistant follows too: a chat reply is never where money moves or a report is read, even
# when the chat is on the website.
_ASSISTANT_CAPABILITIES: dict[ChannelAction, ChannelCapability] = {
    ChannelAction.LEARN: ChannelCapability.FULL,
    ChannelAction.START_INTAKE: ChannelCapability.FULL,
    ChannelAction.UPLOAD_DOCUMENTS: ChannelCapability.HANDOFF,
    ChannelAction.PAY: ChannelCapability.HANDOFF,
    ChannelAction.CHECK_STATUS: ChannelCapability.FULL,
    ChannelAction.VIEW_REPORT: ChannelCapability.HANDOFF,
    ChannelAction.TALK_TO_HUMAN: ChannelCapability.FULL,
    ChannelAction.MANAGE_ACCOUNT: ChannelCapability.NOT_OFFERED,
}



def capability_for(action: ChannelAction) -> ChannelCapability:
    """What the assistant may do with *action* (§26.3.4)."""
    return _ASSISTANT_CAPABILITIES[action]


def require_handoff(action: ChannelAction) -> None:
    """Raise for an action that is not a handoff.

    Asking a `FULL` action for a link is a bug in the caller — it has nothing to hand off —
    and a `NOT_OFFERED` one has nowhere to hand off to; an empty answer would hide the bug.
    """
    if capability_for(action) != ChannelCapability.HANDOFF:
        raise ValueError(f"{action.value} is not a handoff action (§26.3.4).")

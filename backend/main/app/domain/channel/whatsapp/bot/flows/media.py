"""The non-text inbound flow (PRD §26.6.3, §26.1.6 rule 6, WA-06/WA-38).

What happens when a customer sends something other than words — a photo of their survey
plan, a voice note, a location pin.

§26.6.3 gives three answers, and this module is the single place that decides which:

* **Images and documents** — thank them, state the **evidence rule**, and hand over an
  `upload` link. The rule is the point: only portal uploads and structured intake are
  canonical, so a chat image never enters the verification file. But refusing silently is
  not an option either — the person sending it believes they have just submitted a
  document, and "I didn't understand" leaves them believing it.
* **Voice notes** — v1 cannot listen, so it says so and routes to someone who will. Never
  dropped, and never answered as if it had been understood.
* **Pins, contacts, stickers, video** — acknowledged and routed to a person.

**The upload link needs two facts, not one.** An `upload` token names a customer *and* a
case (`ACTION_INTENTS`), so it can only be issued to a number whose account we know, for a
verification we can name. That splits the document row three ways: one open case → the
link; several → ask which, using the **same** numbered list and matcher as the status flow
(`status.choose_prompt` / `status.resolve_choice`), so a customer never has to learn two
ways of answering the same question; none, or unlinked → the rule and the next step, but no
link, because issuing one would attach a stranger's photograph to somebody's verification.

Pure functions over cases the engine already fetched, like every module in `flows/`: the
§26.6.4 adversarial suite exercises this without a database. Minting the token is the
engine's job — a flow module never reaches for a service of its own.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from main.app.domain.channel.whatsapp.bot.flows import status as status_flow
from main.app.domain.channel.whatsapp.bot.flows.status import CaseSummary
from main.app.domain.channel.whatsapp.bot.projection import ChannelState
from main.app.domain.channel.whatsapp.bot.session.models import EscalationReason
from main.appodus_utils.integrations.messaging.providers.whatsapp.inbound import InboundKind

# What the bot can turn into an upload link. Everything else non-text goes to a person.
_DOCUMENT_KINDS = frozenset({InboundKind.IMAGE, InboundKind.DOCUMENT})

# Stages *before* a case has been paid for. There is no verification file to upload into
# yet — the case has not been quoted, so it has no tier — and the upload landing needs both
# to render. Everything from PAID onward is a legitimate target, including a delivered case:
# a customer sending a document during a dispute or a re-check is doing exactly what §26.6.3
# is for, and refusing them would be the same silence the flow exists to prevent.
_PRE_PAYMENT_STATES = frozenset({
    ChannelState.ENQUIRY,
    ChannelState.INTAKE_IN_PROGRESS,
    ChannelState.INTAKE_COMPLETE,
    ChannelState.PAYMENT_PENDING,
})

# Non-text kinds that route to a human, and the reason each is recorded under (§26.10 asks
# for voice-note volume by name, so it is counted apart from media the bot merely cannot
# open). A caption on any of these is not what is being answered — the thing that arrived is.
_ESCALATING_KINDS: dict[InboundKind, EscalationReason] = {
    InboundKind.AUDIO: EscalationReason.VOICE_NOTE,
    InboundKind.VIDEO: EscalationReason.UNSUPPORTED_MEDIA,
    InboundKind.STICKER: EscalationReason.UNSUPPORTED_MEDIA,
    InboundKind.LOCATION: EscalationReason.UNSUPPORTED_MEDIA,
    InboundKind.CONTACTS: EscalationReason.UNSUPPORTED_MEDIA,
    InboundKind.UNSUPPORTED: EscalationReason.UNSUPPORTED_MEDIA,
}


def is_media(kind: InboundKind) -> bool:
    """Whether §26.6.3 owns this turn rather than the ordinary text path.

    TEXT and INTERACTIVE are the only kinds that carry an intent to classify; a menu
    selection is a tap on a button the bot itself offered, not media.
    """
    return kind in _DOCUMENT_KINDS or kind in _ESCALATING_KINDS


@dataclass(frozen=True)
class MediaOutcome:
    """What to say, and what the engine must do about it.

    Exactly one of the three is ever set: a handover, a case to mint a link for, or a
    question with the cases it offered.
    """

    text: str = ""
    escalation_reason: Optional[EscalationReason] = None
    upload_for_vid: Optional[str] = None
    offered_vids: tuple[str, ...] = ()

    @property
    def is_escalation(self) -> bool:
        """Route to a person — `text` is unused, the engine renders the coverage copy."""
        return self.escalation_reason is not None

    @property
    def awaits_choice(self) -> bool:
        """The bot asked which case the document belongs to and is waiting for an answer."""
        return bool(self.offered_vids)


def render(
    kind: InboundKind, is_linked: bool, cases: Sequence[CaseSummary]
) -> MediaOutcome:
    """Decide §26.6.3's answer for one non-text message.

    ``is_linked`` is passed rather than inferred from ``cases`` being empty: a linked
    customer with nothing open and an unlinked number both have no cases, but they need
    different next steps — start a verification, versus link this number first.

    ``cases`` is the customer's full list, as the status flow reads it; the ones that can
    actually receive an upload are selected here rather than by the caller, so the rule
    lives with the flow that depends on it.
    """
    from main.app.domain.channel.whatsapp.bot import content

    escalation_reason = _ESCALATING_KINDS.get(kind)
    if escalation_reason:
        return MediaOutcome(escalation_reason=escalation_reason)

    if not is_linked:
        return MediaOutcome(text=content.document_received_unlinked())
    uploadable = uploadable_cases(cases)
    if not uploadable:
        return MediaOutcome(text=content.document_received_no_case())
    if len(uploadable) == 1:
        return MediaOutcome(upload_for_vid=uploadable[0].vid)
    return MediaOutcome(
        text=content.document_choose_case(status_flow.choose_prompt(uploadable)),
        offered_vids=tuple(case.vid for case in uploadable),
    )


def uploadable_cases(cases: Sequence[CaseSummary]) -> list[CaseSummary]:
    """The customer's cases that a document can be attached to.

    Public because the engine re-derives the offered list when the customer answers "which
    one?" a turn later, and both sides must agree on what was offered — a case that was
    never on the list must not become selectable by naming its reference.
    """
    return [case for case in cases if case.channel_state not in _PRE_PAYMENT_STATES]


def resolve_choice(cases: Sequence[CaseSummary], choice: str) -> Optional[CaseSummary]:
    """Which case the customer named, or ``None`` if they answered something else.

    ``None`` is not a failure — it means they moved on ("actually, what does it cost?"),
    and the engine drops the flow and classifies fresh rather than nagging. Delegated to
    the status flow's matcher so both questions accept the same answers: a position from
    the list, or the case reference.
    """
    return status_flow.resolve_choice(cases, choice)

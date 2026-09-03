"""The pay and report handoff flows (PRD §7.3.4, §7.4.2, WA-17).

§7.3.4 marks three WhatsApp actions `HANDOFF` — upload documents, pay, and view report.
§7.6.3 built the first, because a document arriving is something that *happens to* the bot.
The other two are things a customer **asks** for ("how do I pay?", "send me my report"), and
this module is the flow behind those two turns.

The shape is deliberately §7.6.3's shape. A handoff link names a customer **and** a case
(`ACTION_INTENTS`), so each turn splits the same three ways: one eligible case → the link;
several → ask which, using the **same** numbered list and matcher as the status flow
(`status.choose_prompt` / `status.resolve_choice`), so a customer never has to learn two ways
of answering the same question; none, or an unlinked number → say why, with no link, because
issuing one would mean guessing whose case — and whose money — is involved.

**Eligibility is read off the §7.3.2 projection, never off a raw status.** A case is payable
while it is quoted and unpaid, and readable once delivered — stage names `projection.py`
already owns. Deriving them from `VerificationStatus` here would put the same mapping in a
second place, and the two would drift the day a status is added.

Pure functions over cases the engine already fetched, like every module in `flows/`: minting
the token is the engine's job — a flow module never reaches for a service of its own.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from main.app.domain.channel.whatsapp.bot.capabilities import (
    ChannelAction,
    ChannelCapability,
    capability_for,
)
from main.app.domain.channel.whatsapp.bot.flows import status as status_flow
from main.app.domain.channel.whatsapp.bot.flows.status import CaseSummary
from main.app.domain.channel.whatsapp.bot.projection import ChannelState

# Which §7.3.2 stages each handoff can act on.
#
# `PAY` covers the two stages where money is owed and payable. `INTAKE_COMPLETE` is the
# main one — it projects from `SUBMITTED`, which is a case that has been quoted and not yet
# paid for, and is exactly the state the `/wa/pay/<token>` landing is built to take. Naming
# only `PAYMENT_PENDING` looks right and is wrong: that is the narrower in-flight state, and
# a customer asking "how do I pay?" is almost always sitting at `SUBMITTED`. Before these
# two there is no quote to pay against; after them the case is paid. `media.py` draws the
# same boundary from the other side, in `_PRE_PAYMENT_STATES`.
#
# `VIEW_REPORT` is **`DELIVERED` only**, and the stage it excludes is the trap. Despite its
# name, `ChannelState.REPORT_READY` projects from `VerificationStatus.UNDER_REVIEW` — the
# report exists but has not passed the §8 release gate, and `EventType.REPORT_READY` is not
# published until `release()` has run. Offering a link there would hand the customer an
# unreleased report, which is precisely what the release gate exists to prevent. `DELIVERED`
# also covers `DISPUTED`, and a customer in a dispute re-reading their own report is exactly
# who §7.4.2's "get a new link" recovery is for.
_ELIGIBLE_STATES: dict[ChannelAction, frozenset[ChannelState]] = {
    ChannelAction.PAY: frozenset(
        {ChannelState.INTAKE_COMPLETE, ChannelState.PAYMENT_PENDING}
    ),
    ChannelAction.VIEW_REPORT: frozenset({ChannelState.DELIVERED}),
}


@dataclass(frozen=True)
class HandoffOutcome:
    """What to say, and what the engine must do about it.

    Either a case to mint a link for, or a question with the cases it offered, or neither —
    in which case `text` is the whole answer.
    """

    text: str = ""
    link_for_vid: Optional[str] = None
    offered_vids: tuple[str, ...] = ()

    @property
    def awaits_choice(self) -> bool:
        """The bot asked which case and is waiting for an answer."""
        return bool(self.offered_vids)


def eligible_cases(
    action: ChannelAction, cases: Sequence[CaseSummary]
) -> list[CaseSummary]:
    """The customer's cases this handoff can act on.

    Public because the engine re-derives the offered list when the customer answers "which
    one?" a turn later, and both sides must agree — a case that was never on the list must
    not become selectable by naming its reference.

    Raises for an action that is not a handoff, for the same reason
    `capabilities.handoff_intent_for` does: asking is then a bug in the caller, and an empty
    list would hide it.
    """
    if capability_for(action) != ChannelCapability.HANDOFF:
        raise ValueError(f"{action.value} is not a handoff action on WhatsApp (§7.3.4).")
    states = _ELIGIBLE_STATES[action]
    return [case for case in cases if case.channel_state in states]


def render(
    action: ChannelAction, is_linked: bool, cases: Sequence[CaseSummary]
) -> HandoffOutcome:
    """Decide the answer for one pay-or-report request.

    ``is_linked`` is passed rather than inferred from ``cases`` being empty, exactly as in
    §7.6.3: a linked customer with nothing eligible and an unlinked number both have no
    cases to offer, but they need different next steps.
    """
    from main.app.domain.channel.whatsapp.bot import content

    if not is_linked:
        return HandoffOutcome(text=content.handoff_unlinked(action))

    eligible = eligible_cases(action, cases)
    if not eligible:
        return HandoffOutcome(text=_nothing_eligible(action))
    if len(eligible) == 1:
        return HandoffOutcome(link_for_vid=eligible[0].vid)
    return HandoffOutcome(
        text=_choose(action, status_flow.choose_prompt(eligible)),
        offered_vids=tuple(case.vid for case in eligible),
    )


def resolve_choice(
    cases: Sequence[CaseSummary], choice: str
) -> Optional[CaseSummary]:
    """Which case the customer named, or ``None`` if they answered something else.

    ``None`` is not a failure — it means they moved on, and the engine drops the flow and
    classifies fresh. Delegated to the status flow's matcher so every "which one?" in the
    channel accepts the same answers: a position from the list, or the case reference.
    """
    return status_flow.resolve_choice(cases, choice)


# ─── Copy selection ───────────────────────────────────────────────
#
# The two actions say genuinely different things — one is about money owed, the other about
# a report waiting — so the prose lives in `content` per action rather than being templated
# from a shared sentence with the noun swapped.

def _nothing_eligible(action: ChannelAction) -> str:
    from main.app.domain.channel.whatsapp.bot import content

    if action == ChannelAction.PAY:
        return content.pay_no_case()
    return content.report_no_case()


def _choose(action: ChannelAction, prompt: str) -> str:
    from main.app.domain.channel.whatsapp.bot import content

    if action == ChannelAction.PAY:
        return content.pay_choose_case(prompt)
    return content.report_choose_case(prompt)

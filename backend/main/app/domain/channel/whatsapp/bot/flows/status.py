"""The status flow (PRD §7.3.1, §7.4.3, §7.6.2, WA-07).

"Check my status" is the one bot flow that reads a customer's own case data, which makes
it the flow with the most to get wrong. Three rules shape it:

* **The data is the dashboard's data.** The engine fetches through the same verification
  services the website uses (§7.3.1) and hands the result here; the wording comes from
  `verification/tracking/labels.py`, which the dashboard already renders. A second status
  vocabulary is how two surfaces start disagreeing.
* **The number must be linked.** Identity is resolved before this flow is reached
  (§7.4.3); an unlinked number is answered with an offer to link, never with a case.
* **More than one case means asking, not guessing.** A customer with three verifications
  who says "any update?" gets a numbered list and picks one — an answer about the wrong
  property is worse than a question.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List, Optional, Sequence

from main.app.domain.channel.whatsapp.bot.projection import ChannelState


@dataclass(frozen=True)
class CaseSummary:
    """One verification, as much of it as a chat message should carry.

    Deliberately thin. A chat reply is not a dashboard: it says which property, where the
    case is, and when it is due — everything else belongs behind the customer's login,
    which is exactly the boundary §7.3.4 draws.
    """

    vid: str
    property_label: str
    status_label: str
    channel_state: ChannelState
    sla_due_date: Optional[date] = None
    sla_label: Optional[str] = None


@dataclass(frozen=True)
class StatusOutcome:
    """What the engine should say, and whether it should wait for a choice."""

    text: str
    offered_vids: tuple[str, ...] = ()

    @property
    def awaits_choice(self) -> bool:
        return bool(self.offered_vids)


def render(cases: Sequence[CaseSummary]) -> StatusOutcome:
    """The reply for a "check my status" turn."""
    if not cases:
        return StatusOutcome(_no_cases())
    if len(cases) == 1:
        return StatusOutcome(_one_case(cases[0]))
    return StatusOutcome(_choose_prompt(cases), tuple(case.vid for case in cases))


def render_choice(cases: Sequence[CaseSummary], choice: str) -> Optional[StatusOutcome]:
    """The reply once the customer picks from the list, or ``None`` if they did not.

    ``None`` is not a failure — it means the message was something else entirely ("actually,
    what does it cost?"), and the engine should classify it fresh rather than nag. A flow
    that insisted on an answer would trap a customer who changed their mind.
    """
    selected = resolve_choice(cases, choice)
    return StatusOutcome(_one_case(selected)) if selected else None


def resolve_choice(cases: Sequence[CaseSummary], choice: str) -> Optional[CaseSummary]:
    """Match a reply against the list that was offered.

    Accepts the position ("2") or the case reference, with or without its case. Both are
    on screen in the message the customer is replying to, so both are things a real person
    types — and neither is inferred, so a stray "2 bedrooms" cannot select a case.
    """
    answer = (choice or "").strip()
    if not answer:
        return None
    if answer.isdigit():
        index = int(answer) - 1
        return cases[index] if 0 <= index < len(cases) else None
    normalized = answer.upper()
    for case in cases:
        if case.vid.upper() == normalized:
            return case
    return None


# ─── Copy ─────────────────────────────────────────────────────────

def _no_cases() -> str:
    # Imported lazily: `content` imports settings and pricing DTOs, and this module is
    # meant to stay importable by a test that wants nothing but the branching.
    from main.app.domain.channel.whatsapp.bot import content

    return content.no_cases()


def _one_case(case: CaseSummary) -> str:
    lines = [
        "Here's where your verification stands:",
        "",
        f"📍 {case.property_label}",
        f"Reference: {case.vid}",
        f"Status: {case.status_label}",
    ]
    if case.sla_due_date:
        lines.append(f"Expected by: {case.sla_due_date.strftime('%d %b %Y')}")
    if case.sla_label:
        lines.append(f"Timeline: {case.sla_label}")
    lines += ["", "Sign in at veriprops.ng for the full details and your report."]
    return "\n".join(lines)


def _choose_prompt(cases: Sequence[CaseSummary]) -> str:
    listed: List[str] = [
        f"{position}. {case.property_label} ({case.vid}) — {case.status_label}"
        for position, case in enumerate(cases, start=1)
    ]
    body = "\n".join(listed)
    return (
        f"You have {len(cases)} verifications running. Which one would you like an update "
        f"on?\n\n{body}\n\nReply with the number, or the reference."
    )

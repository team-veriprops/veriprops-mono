"""What one bot turn produces.

A reply is a value, not a side effect: flows build one and the engine sends it. That split
is what lets the §26.6.4 adversarial suite assert on copy and routing without a transport,
a session, or a database.

``escalation_reason`` being set is the difference between "the bot answered" and "the bot
handed over". It is carried on the reply rather than raised, because an escalation is a
normal, successful outcome — §26.6.2 lists three ways to reach it by design.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from main.app.domain.channel.whatsapp.bot.session.models import EscalationReason


@dataclass(frozen=True)
class BotReply:
    """One outbound message, and whether it ends the bot's part in the conversation."""

    text: str
    escalation_reason: Optional[EscalationReason] = None

    @property
    def is_escalation(self) -> bool:
        return self.escalation_reason is not None

"""Phone-number forms shared by every messaging channel.

The app keys a number on E.164 with its leading ``+``. Several providers (Meta's WhatsApp
``wa_id``, Termii's SMS ``to``) want the same digits without it, so each converts at its own
boundary through :func:`digits_of` rather than stripping characters inline.
"""
from __future__ import annotations


def digits_of(number: str) -> str:
    """The number's digits alone: ``+234 801-234-5678`` → ``2348012345678``."""
    return "".join(ch for ch in (number or "") if ch.isdigit())

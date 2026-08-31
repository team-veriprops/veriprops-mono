"""Phone-number forms on the WhatsApp seam.

Two conventions meet here and they are one character apart, which is exactly why they
get confused. Meta identifies a chat participant by `wa_id` — digits only, no `+` — and
the messaging layer validates WhatsApp recipients in that same form. The rest of
Veriprops keys identity on E.164 with the leading `+` (`Utils.normalize_phone`, the
`users.phone` column, the account-linking lookups).

Converting in one place keeps a stray `+` from silently failing an outbound send, or a
missing one from silently failing an identity lookup.
"""
from __future__ import annotations


def digits_of(number: str) -> str:
    return "".join(ch for ch in (number or "") if ch.isdigit())


def to_e164(number: str) -> str:
    """The identity form used across the app: ``+2348012345678``."""
    digits = digits_of(number)
    return f"+{digits}" if digits else ""


def to_wa_recipient(number: str) -> str:
    """The form Meta and the messaging layer accept as a recipient: ``2348012345678``."""
    return digits_of(number)

"""The one official WhatsApp number, projected for the surfaces that publish it.

PRD §7.1.2 (anti-impersonation) makes a single number the customer's way to tell the real
Veriprops from an impersonator — it appears on the website widget, on every certified
report, and in investor materials. Those surfaces must never drift, so all of them read
this module rather than carrying their own copy: ``official_number_digits()`` is the
wa.me-ready form and ``display_number()`` the human-readable one.
"""
from __future__ import annotations

import re

from main.app.config.settings import settings

# A Nigerian E.164 number is a 3-digit country code plus a 10-digit subscriber number,
# published as "+234 916 762 4347" (3-3-4). Any other length is shown ungrouped rather
# than guessed at.
_NG_COUNTRY_CODE_LENGTH = 3
_NG_SUBSCRIBER_LENGTH = 10


def _digits_only(number: str) -> str:
    return re.sub(r"\D", "", number or "")


def official_number_digits() -> str:
    """The configured number as bare digits — the form ``wa.me/<number>`` requires."""
    return _digits_only(settings.WHATSAPP_OFFICIAL_NUMBER)


def display_number(number: str) -> str:
    """The number as customers see it in copy: ``+234 916 762 4347``."""
    digits = _digits_only(number)
    if not digits:
        return ""
    if len(digits) != _NG_COUNTRY_CODE_LENGTH + _NG_SUBSCRIBER_LENGTH:
        return f"+{digits}"
    country, subscriber = digits[:_NG_COUNTRY_CODE_LENGTH], digits[_NG_COUNTRY_CODE_LENGTH:]
    return f"+{country} {subscriber[:3]} {subscriber[3:6]} {subscriber[6:]}"

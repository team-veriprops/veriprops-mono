"""The contact details QA fixtures are given, and how the router recognises them.

`/dev/seed` and `/dev/scenario` create people who need an email and a verified phone. They run
on staging too, where messages go out through live providers, so those details come from two
recognisable ranges, and on staging the router hands a message for either to the QA sink
(`providers/qa_sink.py`) instead of sending it. Locally the fixtures keep Mailpit and the SMS
mock, because the e2e suite reads their mail there.

The phone range is a slice of a real Nigerian prefix: no number range is reserved for fiction in
Nigeria. On staging, a person whose own phone falls inside it would not receive SMS there.
"""
from __future__ import annotations

import secrets

from main.appodus_utils.integrations.messaging.models import MessageChannel

# A non-special-use domain: the email validator rejects reserved TLDs like `.test`.
QA_EMAIL_DOMAIN = "veriprops.io"

# Nigerian local numbers (no leading 0) for fixtures: this prefix plus six digits.
QA_PHONE_LOCAL_PREFIX = "8100"
_NIGERIA_DIAL_CODE = "234"


def qa_local_phone(n: int) -> str:
    """The fixed fixture number *n* (the seed's named personas)."""
    return f"{QA_PHONE_LOCAL_PREFIX}{n:06d}"


def unique_qa_local_phone() -> str:
    """A fixture number no other fixture holds, in all likelihood.

    Sharing a verified phone across accounts is the §17.1 anti-farming signal, so a fixture that
    reused one would quietly void any referral behaviour a spec asserts on."""
    return qa_local_phone(secrets.randbelow(10 ** 6))


def is_qa_recipient(channel: MessageChannel, recipient: str) -> bool:
    """Whether *recipient* is a QA fixture's address on *channel*."""
    if channel == MessageChannel.EMAIL:
        return recipient.lower().endswith(f"@{QA_EMAIL_DOMAIN}")
    if channel in (MessageChannel.SMS, MessageChannel.WHATSAPP):
        return recipient.lstrip("+").startswith(f"{_NIGERIA_DIAL_CODE}{QA_PHONE_LOCAL_PREFIX}")
    return False

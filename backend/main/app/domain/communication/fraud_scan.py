"""Send-time fraud scanner (PRD §4.7, §11.2).

Pure and deterministic — no I/O, no model calls. It flags the off-platform-contact and
payment-solicitation patterns that a mediated, no-direct-contact channel must hold:
phone numbers, emails, URLs, banking/payment details, social handles, and explicit
"take it outside the platform" phrasing.

The scan is synchronous and runs on every send. Most messages carry nothing to flag and
take the fast lane (empty result → delivered immediately); only a genuinely flagged
message is held for admin review. MVP ships a single hold behaviour (no severity tiers,
§4.7) — any non-empty result holds the message. The matched categories are recorded so the
false-positive rate can be instrumented from day one.
"""
from __future__ import annotations

import enum
import re
from typing import List


class FraudCategory(str, enum.Enum):
    """Why a message was flagged (recorded on the held message for instrumentation)."""

    PHONE = "PHONE"
    EMAIL = "EMAIL"
    URL = "URL"
    BANKING = "BANKING"
    SOCIAL = "SOCIAL"
    OFF_PLATFORM = "OFF_PLATFORM"


# A run of 10+ digits, tolerating the usual phone separators (space, dash, dot, parens,
# a leading +). Catches +2348012345678, 0803 123 4567, (080) 123-45678, etc.
_PHONE_RE = re.compile(r"(?:\+?\d[\s().\-]?){9,}\d")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
# Explicit scheme, a www. host, or a bare domain on a common TLD. The bare-domain
# alternative ignores a domain that is part of an email address (preceded by ``@``) or a
# longer host, so ``agent@example.com`` flags EMAIL only, not EMAIL+URL.
_URL_RE = re.compile(
    r"(?:https?://|www\.)\S+"
    r"|(?<![@\w.])[A-Za-z0-9\-]+\.(?:com|net|org|io|co|me|app|ng|xyz|info|biz|dev)\b",
    re.IGNORECASE,
)
# Explicit banking/payment wording. A bare digit run (a NUBAN account or BVN) is not
# matched here — it is caught by the PHONE rule (9+ digits) and held either way — so an
# ordinary phone number is not double-flagged as banking.
_BANKING_RE = re.compile(
    r"\bbvn\b"
    r"|\b(?:account|acct|a/c)\s*(?:number|no|#|\d)"
    r"|\b(?:bank\s*transfer|wire\s*transfer|iban|swift|sort\s*code|routing\s*number)\b",
    re.IGNORECASE,
)
_SOCIAL_RE = re.compile(
    r"(?<!\w)@[A-Za-z0-9_.]{2,}"
    r"|\b(?:whatsapp|wa\.me|telegram|t\.me|instagram|\big\b|snapchat|snap|"
    r"facebook|messenger|signal|viber|dm\s+me|slide\s+into)\b",
    re.IGNORECASE,
)
_OFF_PLATFORM_RE = re.compile(
    r"\b(?:outside|off)\s+(?:the\s+)?(?:platform|app|site|system)\b"
    r"|\boff[-\s]?platform\b"
    r"|\b(?:call|text|reach|contact|message|msg)\s+me\b"
    r"|\breach\s+me\s+on\b"
    r"|\b(?:let'?s|lets)\s+(?:talk|chat|deal|meet)\s+(?:outside|directly|privately)\b"
    r"|\bcontact\s+(?:me\s+)?directly\b",
    re.IGNORECASE,
)

_RULES = [
    (FraudCategory.EMAIL, _EMAIL_RE),
    (FraudCategory.URL, _URL_RE),
    (FraudCategory.SOCIAL, _SOCIAL_RE),
    (FraudCategory.BANKING, _BANKING_RE),
    (FraudCategory.OFF_PLATFORM, _OFF_PLATFORM_RE),
    (FraudCategory.PHONE, _PHONE_RE),
]


def scan_message(body: str) -> List[FraudCategory]:
    """Return the fraud categories a message body matches (empty = clean → fast lane).

    Order is stable (rule declaration order) so results are deterministic and testable.
    """
    if not body:
        return []
    return [category for category, pattern in _RULES if pattern.search(body)]


def is_clean(body: str) -> bool:
    """True when a message carries nothing flaggable and may deliver immediately (§4.7)."""
    return not scan_message(body)

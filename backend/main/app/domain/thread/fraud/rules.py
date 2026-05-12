"""Fraud detection regex rules (S38)."""
from __future__ import annotations

import re
from typing import List

# Each pattern: (name, compiled_regex)
_RULES: list[tuple[str, re.Pattern]] = [
    ("phone", re.compile(r"\+?[\d\s\-]{10,}", re.IGNORECASE)),
    ("email", re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", re.IGNORECASE)),
    ("url", re.compile(r"https?://\S+", re.IGNORECASE)),
    ("banking", re.compile(
        r"\b(account\s+number|sort\s+code|IBAN|BVN|NIN|routing\s+number|bank\s+transfer)\b",
        re.IGNORECASE,
    )),
    ("off_platform", re.compile(
        r"\b(contact\s+me\s+directly|whatsapp\s+me|call\s+me\s+at|reach\s+me\s+on|"
        r"outside\s+the\s+platform|off[\s\-]platform|my\s+number\s+is)\b",
        re.IGNORECASE,
    )),
]


def scan(body: str) -> List[str]:
    """Return a list of matched pattern names for *body* (empty = clean)."""
    matched = []
    for name, pattern in _RULES:
        if pattern.search(body):
            matched.append(name)
    return matched

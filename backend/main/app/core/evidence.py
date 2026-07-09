"""Evidence content-hash helper — PRD §4.5.

On evidence upload we compute and store a **SHA-256 content hash of the file**
(per item, not chained). Combined with object-store immutability and the audit
log, this makes any post-submission alteration *detectable*: the stored hash no
longer matches the bytes. This proves integrity *after receipt*; authenticity
*at capture* (server-side GPS / timestamp) is a separate control (§7.3a).
"""
from __future__ import annotations

import hashlib
import hmac

_HASH_HEX_LENGTH = 64  # SHA-256 → 32 bytes → 64 hex chars


def compute_content_hash(data: bytes) -> str:
    """Return the lowercase SHA-256 hex digest of ``data``."""
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("evidence content must be bytes")
    return hashlib.sha256(bytes(data)).hexdigest()


def verify_content_hash(data: bytes, expected_hash: str) -> bool:
    """Constant-time check that ``data`` still hashes to ``expected_hash``.

    Case-insensitive on the expected digest. Returns ``False`` (never raises) on
    a malformed expected value, so callers can treat it as a tamper signal.
    """
    if not expected_hash or len(expected_hash) != _HASH_HEX_LENGTH:
        return False
    return hmac.compare_digest(compute_content_hash(data), expected_hash.lower())

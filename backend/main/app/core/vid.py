"""Verification-ID (VID) generator — PRD §4.10.

The VID keeps its human-readable shape ``VP-YYYY-XXXXXX`` but ``XXXXXX`` is a
**high-entropy, non-sequential** suffix — never a guessable counter. The public
lookup (`/verify/[id]`) is an unauthenticated enumeration surface, so a walkable
ID space would let an attacker scrape it; a random suffix closes that vector
(alongside rate-limiting + indistinguishable responses, added with the lookup
endpoint). Any "how many verifications" metric is served by a separate internal
counter, never by the VID.

Uniqueness against persisted rows is enforced at the call site (a unique column
on the verifications table) once that domain is rebuilt; this module only
guarantees the format and the entropy of the suffix.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timezone

# Crockford-style alphabet: uppercase, ambiguity-free (no I, L, O, U, 0, 1).
# 30 symbols ^ 6 ≈ 7.3e8 combinations — ample entropy for the public surface.
VID_ALPHABET = "ABCDEFGHJKMNPQRSTVWXYZ23456789"
VID_SUFFIX_LENGTH = 6
VID_PREFIX = "VP"


def generate_vid(year: int | None = None) -> str:
    """Return a fresh ``VP-YYYY-XXXXXX`` VID with a random, non-sequential suffix.

    :param year: override the year segment (defaults to the current UTC year).
    """
    yyyy = year if year is not None else datetime.now(timezone.utc).year
    suffix = "".join(secrets.choice(VID_ALPHABET) for _ in range(VID_SUFFIX_LENGTH))
    return f"{VID_PREFIX}-{yyyy:04d}-{suffix}"

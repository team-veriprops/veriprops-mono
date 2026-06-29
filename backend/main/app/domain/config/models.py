"""Public runtime configuration exposed to the frontend.

The backend is the single source of truth for these flags; the frontend reads
them rather than duplicating env vars (e.g. NEXT_PUBLIC_*)."""
from __future__ import annotations

from main.appodus_utils import Object


class PublicConfigDto(Object):
    # Whether phone verification is enforced anywhere in the product. The frontend
    # shows/skips the phone-verify step based on this.
    phone_verification_enabled: bool

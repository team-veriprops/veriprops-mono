"""Public runtime flags the frontend reads instead of holding its own copy."""
from __future__ import annotations

from main.appodus_utils import Object


class PublicConfigDto(Object):
    # Drives whether the signup flow shows the phone-verification step.
    phone_verification_enabled: bool

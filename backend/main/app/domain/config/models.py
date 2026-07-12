"""Public runtime flags the frontend reads instead of holding its own copy."""
from __future__ import annotations

from main.appodus_utils import Object


class PublicConfigDto(Object):
    # Drives whether the signup flow shows the phone-verification step.
    phone_verification_enabled: bool
    # §B go-live gate (D18): whether the Premium Legal Opinion report section is live.
    legal_opinion_enabled: bool = False
    # Chat message body cap — the frontend input maxLength reads this rather than
    # hardcoding its own value (backend is the source of truth).
    chat_message_max_length: int = 2000

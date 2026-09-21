"""Outbound policy shared by every WhatsApp transport.

Rules that must hold no matter which provider is selected live here, so the live Cloud
API path and the deterministic stub cannot drift — and so CI, which runs on the stub,
actually exercises them.
"""
from __future__ import annotations

from typing import Any

from main.appodus_utils.integrations.messaging.models import WhatsappMediaType


def assert_no_outbound_voice(payload: Any) -> None:
    """Enforce the standing no-outbound-voice rule (PRD §26.1.5).

    Official Veriprops communication is text from the verified number; a voice note
    claiming to be Veriprops is an impersonation signal. The ban lives at the transport
    boundary so no future flow can route around it.
    """
    if getattr(payload, "media_type", None) == WhatsappMediaType.AUDIO:
        raise ValueError(
            "Veriprops never sends voice notes (PRD §26.1.5) — refusing to send audio."
        )

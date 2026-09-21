"""The assistant's WhatsApp surface (PRD §26.6, D93).

The engine and its rules live in `communication/assistant/`, shared with the portal. What
stays here is WhatsApp's alone: the surface adapter (`surface`), delivery over Meta
(`sender`), non-text media (`flows/media`), and the intake link's redemption
(`intake_handoff`, `intake_controller`).
"""
from main.app.domain.channel.whatsapp.bot import flows  # noqa: F401
from main.app.domain.channel.whatsapp.bot import intake_controller  # noqa: F401
from main.app.domain.channel.whatsapp.bot import intake_handoff  # noqa: F401
from main.app.domain.channel.whatsapp.bot import sender  # noqa: F401
from main.app.domain.channel.whatsapp.bot import surface  # noqa: F401

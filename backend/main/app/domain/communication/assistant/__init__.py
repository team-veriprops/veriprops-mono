"""The assistant (PRD §26.6, §16.7, D93) — one engine answering on every customer surface.

The engine is a dispatcher; the rules it dispatches through live in their own modules so each
is auditable on its own: `guardrails` (what may never be answered), `capabilities` (§26.3.4,
what the assistant offers at all), `content` (every word, code-owned), `projection` (§26.3.2
stage names derived from the real status machine), and `flows/` (pure branching over data the
engine fetched). `surface` is the contract with the channel a turn arrived on: `web` here,
`channel/whatsapp/bot/surface` for WhatsApp.
"""
from main.app.domain.communication.assistant import capabilities  # noqa: F401
from main.app.domain.communication.assistant import content  # noqa: F401
from main.app.domain.communication.assistant import engine  # noqa: F401
from main.app.domain.communication.assistant import flows  # noqa: F401
from main.app.domain.communication.assistant import guardrails  # noqa: F401
from main.app.domain.communication.assistant import intake_seeder  # noqa: F401
from main.app.domain.communication.assistant import projection  # noqa: F401
from main.app.domain.communication.assistant import reply  # noqa: F401
from main.app.domain.communication.assistant import session  # noqa: F401
from main.app.domain.communication.assistant import support_hours  # noqa: F401
from main.app.domain.communication.assistant import surface  # noqa: F401
from main.app.domain.communication.assistant import web  # noqa: F401

"""The WhatsApp bot (PRD §7.6) — the conversation layer over the same backend.

The engine is a dispatcher; the rules it dispatches through live in their own modules so
each is auditable on its own: `guardrails` (what may never be answered), `capabilities`
(§7.3.4, what this surface offers at all), `content` (every word, code-owned), `projection`
(§7.3.2 stage names derived from the real status machine), and `flows/` (pure branching
over data the engine fetched).
"""
from main.app.domain.channel.whatsapp.bot import capabilities  # noqa: F401
from main.app.domain.channel.whatsapp.bot import content  # noqa: F401
from main.app.domain.channel.whatsapp.bot import engine  # noqa: F401
from main.app.domain.channel.whatsapp.bot import flows  # noqa: F401
from main.app.domain.channel.whatsapp.bot import guardrails  # noqa: F401
from main.app.domain.channel.whatsapp.bot import intake_controller  # noqa: F401
from main.app.domain.channel.whatsapp.bot import intake_handoff  # noqa: F401
from main.app.domain.channel.whatsapp.bot import projection  # noqa: F401
from main.app.domain.channel.whatsapp.bot import reply  # noqa: F401
from main.app.domain.channel.whatsapp.bot import sender  # noqa: F401
from main.app.domain.channel.whatsapp.bot import session  # noqa: F401
from main.app.domain.channel.whatsapp.bot import support_hours  # noqa: F401

"""Bot conversation flows (PRD §26.6.2).

Each module here is one flow, written as **pure functions over data the engine already
fetched**. Nothing in this package touches a session, a repository or a transport, which
is what makes the §26.6.4 adversarial suite able to assert on the exact words a customer
would read without standing up a stack.

The engine owns I/O and state; a flow owns wording and branching. That split is also what
keeps §26.3.1 honest — the data a flow renders came from the same services the website
dashboard reads, because the flow had no other way to get it.
"""
from main.app.domain.channel.whatsapp.bot.flows import intake  # noqa: F401
from main.app.domain.channel.whatsapp.bot.flows import status  # noqa: F401

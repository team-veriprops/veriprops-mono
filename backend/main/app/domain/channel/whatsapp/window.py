"""Meta's 24-hour customer service window (PRD §26.7, WA-41).

Meta lets a business send free-form text only within 24 hours of the customer's last
message. Outside it, the only thing that will be delivered is an approved template — which
is why §26.7 carries `window_reopen` at all.

Most of the channel never has to ask: a bot reply is answering a message that just
arrived, so it is inside the window by construction, and every §26.7 template is
business-initiated, so it is outside. The one place the question is genuinely open is an
**agent** replying from the console, possibly hours later — S7's adapter, which is this
module's consumer.

The answer comes from the inbound journal rather than a new column: `whatsapp_inbound_messages`
already records when each message arrived, and deriving the window from it means the two
can never disagree.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from kink import inject

from main.app.domain.channel.whatsapp.inbound.repo import WhatsAppInboundMessageRepo
from main.appodus_utils import Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.integrations.messaging.providers.whatsapp.phone import to_e164

# Meta's service window. Not a setting: it is their policy, and a local override would
# only let us be confidently wrong about what they will deliver.
SERVICE_WINDOW = timedelta(hours=24)


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class WhatsAppWindowService:
    def __init__(self, whatsapp_inbound_message_repo: WhatsAppInboundMessageRepo):
        self._whatsapp_inbound_message_repo = whatsapp_inbound_message_repo

    async def is_open(self, phone: str) -> bool:
        """Whether free-form text will still be delivered to *phone*.

        A number that has never written to us is closed, not open — the safe direction:
        the cost of a needless template is a template, while the cost of a wrongly-assumed
        open window is a message the customer never receives.
        """
        last_inbound_at = await self._whatsapp_inbound_message_repo.last_received_at(
            to_e164(phone)
        )
        if last_inbound_at is None:
            return False
        return Utils.datetime_now() - last_inbound_at < SERVICE_WINDOW

    async def last_inbound_at(self, phone: str) -> Optional[datetime]:
        """When the number last wrote to us — what the console shows beside the window."""
        return await self._whatsapp_inbound_message_repo.last_received_at(to_e164(phone))

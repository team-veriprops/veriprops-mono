"""The inbound journal write: the one step that must succeed before Meta is told "received".

Recorded in its own committed transaction (`INDEPENDENT`), so a message survives whatever
later fails while it is shown in the console or answered. The write is an
`INSERT … ON CONFLICT (wamid) DO NOTHING`: Meta's redeliveries, even concurrent ones, journal
a message exactly once.
"""
from __future__ import annotations

from kink import inject

from main.app.domain.channel.whatsapp.inbound.models import CreateWhatsAppInboundMessageDto
from main.app.domain.channel.whatsapp.inbound.repo import WhatsAppInboundMessageRepo
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import TransactionSessionPolicy, transactional


@inject
@decorate_all_methods(
    transactional(session_policy=TransactionSessionPolicy.INDEPENDENT),
    exclude=["__init__"], exclude_startswith=["_"],
)
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class WhatsAppInboundJournal:
    def __init__(self, whatsapp_inbound_message_repo: WhatsAppInboundMessageRepo):
        self._repo = whatsapp_inbound_message_repo

    async def record(self, message: CreateWhatsAppInboundMessageDto) -> bool:
        """Journal *message*; False when this wamid was already journalled."""
        _, created = await self._repo.insert_or_get(message.model_dump(by_alias=False), ["wamid"])
        return created

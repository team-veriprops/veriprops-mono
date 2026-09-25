"""Backstop for inbound WhatsApp messages journalled but never shown in the console.

A message whose surfacing failed stays journalled and unprocessed. The number's next message
catches it up; this sweep covers a customer who never writes again. On serverless, where
the in-process scheduler is unreliable, the catch-up is the path and this is the net.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from kink import di, inject

from main.app.jobs.exclusive import exclusive_job
from main.app.domain.channel.whatsapp.inbound.service import WhatsAppInboundService
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.transactional import TransactionSessionPolicy, transactional

if TYPE_CHECKING:
    from loguru import Logger

logger: Logger = di['logger']


@inject
@decorate_all_methods(
    transactional(session_policy=TransactionSessionPolicy.ALWAYS_NEW), exclude=['__init__']
)
class WhatsAppInboundSweepJobs:
    """Fresh-session wrapper around the stale-inbound reprocessing sweep."""

    def __init__(self, whatsapp_inbound_service: WhatsAppInboundService):
        self._inbound = whatsapp_inbound_service

    @exclusive_job("unprocessed_whatsapp_inbound")
    async def run_unprocessed_inbound_sweep(self) -> Optional[int]:
        return await self._inbound.reprocess_stale()


async def check_unprocessed_whatsapp_inbound() -> None:
    surfaced = await di[WhatsAppInboundSweepJobs].run_unprocessed_inbound_sweep()
    if surfaced:
        logger.info("whatsapp-inbound sweep: surfaced {} stale message(s)", surfaced)

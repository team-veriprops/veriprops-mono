"""Scheduled-broadcast send sweep (PRD §18.1, decision-log S22).

Sends admin broadcasts whose scheduled time has passed. The sweep logic lives on
``BroadcastService``; this module wraps it in an ``ALWAYS_NEW`` transactional job
(fresh session per sweep, claim-based so a broadcast is sent once). Cadence is
registered in ``app/jobs/scheduled.py``; disabled under test — tests call
``sweep_scheduled_broadcasts`` directly.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from kink import di, inject

from main.app.domain.broadcast.service import BroadcastService
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.transactional import transactional, TransactionSessionPolicy

if TYPE_CHECKING:
    from loguru import Logger

logger: Logger = di['logger']


@inject
@decorate_all_methods(
    transactional(session_policy=TransactionSessionPolicy.ALWAYS_NEW), exclude=['__init__']
)
class BroadcastSweepJobs:
    """Fresh-session wrapper around the scheduled-broadcast send sweep (§18.1, S22)."""

    def __init__(self, broadcast_service: BroadcastService):
        self._broadcast = broadcast_service

    async def run_scheduled_broadcast_sweep(self) -> int:
        return await self._broadcast.sweep_scheduled_broadcasts()


async def check_scheduled_broadcasts() -> None:
    sent = await di[BroadcastSweepJobs].run_scheduled_broadcast_sweep()
    if sent:
        logger.info("broadcast sweep sent {} scheduled broadcast(s)", sent)

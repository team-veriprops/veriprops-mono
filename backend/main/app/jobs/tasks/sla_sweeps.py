"""SLA-breach sweep (PRD §12.2 / §6.4 SLA shedding, decision-log D23).

Flags verifications whose SLA has been breached and publishes the ``SlaBreached``
domain event (customer + ops notifications fan out via the event bus). The sweep
logic lives on ``SlaMonitorService``; this module wraps it in an ``ALWAYS_NEW``
transactional job (fresh session per sweep, idempotent on an existing SLA-breach
notification). Cadence is registered in ``app/jobs/scheduled.py``; disabled under
test — tests call ``sweep_sla_breaches`` directly.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from kink import di, inject

from main.app.domain.verification.sla_monitor import SlaMonitorService
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.transactional import transactional, TransactionSessionPolicy

if TYPE_CHECKING:
    from loguru import Logger

logger: Logger = di['logger']


@inject
@decorate_all_methods(
    transactional(session_policy=TransactionSessionPolicy.ALWAYS_NEW), exclude=['__init__']
)
class SlaMonitorJobs:
    """Fresh-session wrapper around the SLA-breach sweep (§12.2, D23)."""

    def __init__(self, sla_monitor: SlaMonitorService):
        self._sla_monitor = sla_monitor

    async def run_sla_breach_sweep(self) -> int:
        return await self._sla_monitor.sweep_sla_breaches()


async def check_sla_breaches() -> None:
    flagged = await di[SlaMonitorJobs].run_sla_breach_sweep()
    if flagged:
        logger.info("SLA-breach sweep flagged {} verification(s)", flagged)

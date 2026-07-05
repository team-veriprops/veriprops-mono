"""SLA-breach monitor (PRD §12.2, §6.4, D23).

A periodic sweep that finds verifications past their SLA due date and publishes an
``SlaBreached`` event **once** per verification (idempotent on an existing SLA-breach
notification). Publishing goes through the §4.8 bus, so the customer gets the in-app +
email/SMS "taking longer than planned" notification and the SSE nudge, with no source
duplicated. Orchestration-only — no entity of its own.
"""
from __future__ import annotations

from kink import inject

from main.app.core.events import DomainEvent, EventType, publish_domain_event
from main.app.core.realtime import VerificationEventType
from main.app.core.sla import ACTIVE_SLA_STATES
from main.app.domain.notification.repo import NotificationRepo
from main.app.domain.verification.repo import VerificationRepo
from main.appodus_utils import Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class SlaMonitorService:
    def __init__(self, verification_repo: VerificationRepo, notification_repo: NotificationRepo):
        self._verifications = verification_repo
        self._notifications = notification_repo

    async def sweep_sla_breaches(self) -> int:
        """Publish ``SlaBreached`` for each newly-overdue verification. Returns the count
        newly flagged. Idempotent: a verification already carrying an SLA-breach notification
        is skipped, so a repeated sweep does not re-notify."""
        today = Utils.datetime_now().date()
        overdue = await self._verifications.list_active_overdue(list(ACTIVE_SLA_STATES), today)
        flagged = 0
        for verification in overdue:
            already = await self._notifications.exists_for_ref(
                EventType.SLA_BREACHED.value, verification.id
            )
            if already:
                continue
            await publish_domain_event(DomainEvent(
                type=EventType.SLA_BREACHED,
                verification_id=verification.id,
                recipient_user_ids=(verification.customer_id,),
                sse_event=VerificationEventType.STATUS_CHANGED.value,
                data={"vid": verification.vid},
            ))
            flagged += 1
        return flagged

"""SLA-breach monitor (PRD §12.2, §6.4, D23).

A periodic sweep that finds verifications past their SLA due date and publishes an
``SlaBreached`` event **once** per verification: each is claimed (``sla_breach_notified_at``)
in one conditional update before the event goes out, so overlapping runs announce it once. Publishing goes through the §4.8 bus, so the customer gets the in-app +
email/SMS "taking longer than planned" notification and the SSE nudge, with no source
duplicated. Orchestration-only — no entity of its own.
"""
from __future__ import annotations

from kink import inject

from main.app.core.events import DomainEvent, EventType, publish_domain_event
from main.app.core.realtime import VerificationEventType
from main.app.core.sla import ACTIVE_SLA_STATES
from main.app.domain.user.repo import UserRepo
from main.app.domain.verification.repo import VerificationRepo
from main.appodus_utils import Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class SlaMonitorService:
    def __init__(
        self,
        verification_repo: VerificationRepo,
        user_repo: UserRepo,
    ):
        self._verifications = verification_repo
        self._users = user_repo

    async def sweep_sla_breaches(self) -> int:
        """Publish ``SlaBreached`` for each newly-overdue verification. Returns the count
        newly flagged. Each is claimed first, so a scheduled run and an admin-triggered one
        landing together announce it once, and nothing re-announces it later."""
        now = Utils.datetime_now()
        today = now.date()
        overdue = await self._verifications.list_active_overdue(list(ACTIVE_SLA_STATES), today)
        if not overdue:
            return 0
        # §12.2 admin SLA-breach: notify the ops team alongside the customer (one event,
        # so admins share the customer's portal link; admins primarily act from the SLA panel).
        admin_ids = tuple(a.id for a in await self._users.list_admins())
        flagged = 0
        for verification in overdue:
            vid = Utils.uuid_to_hex(verification.id)  # entity ref → wire (hex) form
            if await self._verifications.claim_transition(
                verification.id, [verification.status],
                expect={"sla_breach_notified_at": None}, sla_breach_notified_at=now,
            ) is None:
                continue  # another run announced it
            await publish_domain_event(DomainEvent(
                type=EventType.SLA_BREACHED,
                verification_id=vid,
                recipient_user_ids=(str(verification.customer_id), *(str(a) for a in admin_ids)),
                sse_event=VerificationEventType.STATUS_CHANGED.value,
                data={"vid": verification.vid},
            ))
            flagged += 1
        return flagged

"""Broadcast service (PRD §18.1, D37).

Owns admin announcements: compose (draft or scheduled), preview the audience size, send
now, cancel, and list. Fan-out reuses the §4.8 event bus — one BROADCAST_ANNOUNCEMENT
event per send carrying the resolved recipient ids, so the notification subscriber creates
the per-user in-app + email exactly as any other event. Scheduled sends fire from a sweep.
"""
from __future__ import annotations

from typing import List, Tuple

from kink import inject

from main.app.core.events import DomainEvent, EventType, publish_domain_event
from main.app.domain.audit.models import AuditActionType
from main.app.domain.audit.service import AuditLogService
from main.app.domain.broadcast.models import (
    Broadcast,
    BroadcastAudience,
    BroadcastPreviewDto,
    BroadcastStatus,
    ComposeBroadcastDto,
    CreateBroadcastDto,
)
from main.app.domain.broadcast.repo import BroadcastRepo
from main.app.domain.user.auth.session.models import UserPersona, UserType
from main.app.domain.user.repo import UserRepo
from main.appodus_utils import Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import (
    InvalidResourceStateException,
    ResourceNotFoundException,
)

# A broadcast that can still be sent or cancelled.
_UNSENT = [BroadcastStatus.DRAFT, BroadcastStatus.SCHEDULED]


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class BroadcastService:
    def __init__(self, broadcast_repo: BroadcastRepo, user_repo: UserRepo, audit_service: AuditLogService):
        self._broadcast_repo = broadcast_repo
        self._users = user_repo
        self._audit = audit_service

    async def compose(self, dto: ComposeBroadcastDto, admin_id: str) -> Broadcast:
        status = BroadcastStatus.SCHEDULED if dto.scheduled_at is not None else BroadcastStatus.DRAFT
        broadcast = await self._broadcast_repo.create_return_model(CreateBroadcastDto(
            audience=dto.audience.value, subject=dto.subject, body=dto.body,
            status=status, scheduled_at=dto.scheduled_at, created_by=admin_id,
        ))
        self._audit.schedule(
            action=AuditActionType.ADMIN_CONFIG_CHANGED,
            resource_type="broadcast", resource_id=broadcast.id, actor_id=admin_id,
            details={"audience": dto.audience.value, "status": status.value},
        )
        return broadcast

    async def preview(self, audience: BroadcastAudience) -> BroadcastPreviewDto:
        return BroadcastPreviewDto(audience=audience, recipient_count=len(await self._resolve_recipients(audience)))

    async def send_now(self, broadcast_id: str, admin_id: str) -> Broadcast:
        broadcast = await self._broadcast_repo.get_model(broadcast_id)
        if broadcast is None:
            raise ResourceNotFoundException(resource="broadcast")
        if broadcast.status == BroadcastStatus.SENT.value:
            return broadcast  # idempotent — never re-fan-out a sent broadcast
        if broadcast.status == BroadcastStatus.CANCELLED.value:
            raise InvalidResourceStateException(resource="broadcast", message="This broadcast was cancelled.")
        if not await self._dispatch(broadcast):
            # The scheduled sweep (or another send) got there first, or it was cancelled.
            current = await self._broadcast_repo.get_model(broadcast_id)
            if current.status == BroadcastStatus.CANCELLED.value:
                raise InvalidResourceStateException(resource="broadcast", message="This broadcast was cancelled.")
            return current
        self._audit.schedule(
            action=AuditActionType.ADMIN_CONFIG_CHANGED,
            resource_type="broadcast", resource_id=broadcast.id, actor_id=admin_id,
            details={"action": "send_now"},
        )
        return await self._broadcast_repo.get_model(broadcast_id)

    async def cancel(self, broadcast_id: str, admin_id: str) -> Broadcast:
        broadcast = await self._broadcast_repo.get_model(broadcast_id)
        if broadcast is None:
            raise ResourceNotFoundException(resource="broadcast")
        if broadcast.status == BroadcastStatus.SENT.value:
            raise InvalidResourceStateException(resource="broadcast", message="A sent broadcast cannot be cancelled.")
        cancelled = await self._broadcast_repo.claim_transition(
            broadcast.id, _UNSENT, BroadcastStatus.CANCELLED,
        )
        if cancelled is not None:
            return cancelled
        current = await self._broadcast_repo.get_model(broadcast_id)
        if current.status == BroadcastStatus.SENT.value:
            raise InvalidResourceStateException(resource="broadcast", message="A sent broadcast cannot be cancelled.")
        return current

    async def list_page(self, page: int, page_size: int, status: str | None = None) -> Tuple[List[Broadcast], int]:
        return await self._broadcast_repo.page_all(page, page_size, status)

    async def get(self, broadcast_id: str) -> Broadcast:
        broadcast = await self._broadcast_repo.get_model(broadcast_id)
        if broadcast is None:
            raise ResourceNotFoundException(resource="broadcast")
        return broadcast

    async def sweep_scheduled_broadcasts(self) -> int:
        """Send SCHEDULED broadcasts whose time has passed (§18.1). Idempotent — a SENT
        broadcast is never revisited. Returns the number dispatched."""
        now = Utils.datetime_now()
        sent = 0
        for broadcast in await self._broadcast_repo.list_due_scheduled(now):
            if await self._dispatch(broadcast, from_statuses=[BroadcastStatus.SCHEDULED]):
                sent += 1
        return sent

    # ── helpers ───────────────────────────────────────────────────

    async def _dispatch(self, broadcast: Broadcast, from_statuses=None) -> bool:
        """Send the broadcast, once: claimed as SENT before the fan-out, so a sweep and a
        "send now" (or two overlapping sweeps) cannot both announce it. Whether this call sent it."""
        sent = await self._broadcast_repo.claim_transition(
            broadcast.id, from_statuses or _UNSENT, BroadcastStatus.SENT, sent_at=Utils.datetime_now(),
        )
        if sent is None:
            return False
        recipients = await self._resolve_recipients(BroadcastAudience(broadcast.audience))
        # One event carrying every recipient — the notification subscriber creates the
        # per-user in-app + email (§4.8 fan-out). Best-effort per subscriber.
        await publish_domain_event(DomainEvent(
            type=EventType.BROADCAST_ANNOUNCEMENT,
            recipient_user_ids=tuple(recipients),
            data={"subject": broadcast.subject, "body": broadcast.body},
        ))
        sent.recipient_count = len(recipients)
        return True

    async def _resolve_recipients(self, audience: BroadcastAudience) -> List[str]:
        rows = await self._users.list_recipient_rows()
        out: List[str] = []
        for user_id, user_type, personas in rows:
            if audience == BroadcastAudience.ALL:
                out.append(user_id)
            elif audience == BroadcastAudience.ADMINS and user_type == UserType.ADMIN.value:
                out.append(user_id)
            elif audience == BroadcastAudience.CUSTOMERS and UserPersona.CUSTOMER.value in personas:
                out.append(user_id)
            elif audience == BroadcastAudience.AGENTS and UserPersona.AGENT.value in personas:
                out.append(user_id)
        return out

"""Broadcast service (PRD §18.1, D37).

Owns admin announcements: compose (draft or scheduled), preview the audience size, send, cancel,
list, and the fan-out.

Sending is two steps, so a broadcast to every user never runs inside one request:

1. **Claim.** "Send now", or the scheduled sweep once its time has come, moves the broadcast
   DRAFT/SCHEDULED → SENDING and records the audience size.
2. **Fan-out.** The audience is walked in keyset pages of `BROADCAST_FANOUT_PAGE_SIZE` users. Each
   page is one claim on the broadcast's cursor, so two runners never send the same page, and
   **one** BROADCAST_ANNOUNCEMENT event carrying that page's recipients; the notification
   subscriber writes their in-app entries and queues their emails for the message drain. The
   last page moves the broadcast to SENT.

"Send now" runs the first page inside the request, in a savepoint: an audience that fits one page
is SENT when the request returns, and a page that fails there rolls back alone (cursor, in-app
entries and queued emails together), leaving the broadcast SENDING for the next tick to retry
from the same cursor. Later pages run from the `broadcast_fanout` job on every sweep tick.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from kink import inject

from main.app.config.settings import settings
from main.app.core.events import DomainEvent, EventType, publish_domain_event
from main.app.domain.audit.models import AuditActionType
from main.app.domain.audit.service import AuditLogService
from main.app.domain.broadcast.models import (
    ACTION_FROM_STATUSES,
    Broadcast,
    BroadcastAction,
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
from main.appodus_utils.db.session import get_db_session_from_context
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import (
    InvalidResourceStateException,
    ResourceNotFoundException,
)
from main.appodus_utils.exception.faults import log_fault_once

# Each audience as the recipient filter it runs in SQL: (user type, persona).
_AUDIENCE_FILTER: Dict[BroadcastAudience, Tuple[Optional[UserType], Optional[UserPersona]]] = {
    BroadcastAudience.ALL: (None, None),
    BroadcastAudience.ADMINS: (UserType.ADMIN, None),
    BroadcastAudience.CUSTOMERS: (None, UserPersona.CUSTOMER),
    BroadcastAudience.AGENTS: (None, UserPersona.AGENT),
}


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
        return BroadcastPreviewDto(audience=audience, recipient_count=await self._count(audience))

    async def send_now(self, broadcast_id: str, admin_id: str) -> Broadcast:
        """Start sending, and send the first page before returning. Idempotent: a broadcast
        already SENDING or SENT is returned as it is, never fanned out again."""
        broadcast = await self._get(broadcast_id)
        if broadcast.status == BroadcastStatus.CANCELLED.value:
            raise InvalidResourceStateException(resource="broadcast", message="This broadcast was cancelled.")
        claimed = await self._start(broadcast, ACTION_FROM_STATUSES[BroadcastAction.SEND])
        if claimed is None:
            # Already sending or sent (the scheduled sweep or another send got there first),
            # or it was cancelled meanwhile.
            current = await self._get(broadcast_id)
            if current.status == BroadcastStatus.CANCELLED.value:
                raise InvalidResourceStateException(resource="broadcast", message="This broadcast was cancelled.")
            return current
        self._audit.schedule(
            action=AuditActionType.ADMIN_CONFIG_CHANGED,
            resource_type="broadcast", resource_id=claimed.id, actor_id=admin_id,
            details={"action": "send_now"},
        )
        await self._fanout_page_in_savepoint(claimed)
        return await self._get(broadcast_id)

    async def cancel(self, broadcast_id: str, admin_id: str) -> Broadcast:
        """Stop a broadcast that has not finished. Mid-send, the pages not yet sent are dropped;
        recipients already reached keep their notice, and emails already queued still go out."""
        broadcast = await self._get(broadcast_id)
        if broadcast.status == BroadcastStatus.SENT.value:
            raise InvalidResourceStateException(resource="broadcast", message="A sent broadcast cannot be cancelled.")
        cancelled = await self._broadcast_repo.claim_transition(
            broadcast.id, ACTION_FROM_STATUSES[BroadcastAction.CANCEL], BroadcastStatus.CANCELLED,
        )
        if cancelled is not None:
            self._audit.schedule(
                action=AuditActionType.ADMIN_CONFIG_CHANGED,
                resource_type="broadcast", resource_id=cancelled.id, actor_id=admin_id,
                details={"action": "cancel", "recipients_reached": cancelled.recipients_enqueued or 0},
            )
            return cancelled
        current = await self._get(broadcast_id)
        if current.status == BroadcastStatus.SENT.value:
            raise InvalidResourceStateException(resource="broadcast", message="A sent broadcast cannot be cancelled.")
        return current

    async def list_page(self, page: int, page_size: int, status: str | None = None) -> Tuple[List[Broadcast], int]:
        return await self._broadcast_repo.page_all(page, page_size, status)

    async def get(self, broadcast_id: str) -> Broadcast:
        return await self._get(broadcast_id)

    async def sweep_scheduled_broadcasts(self) -> int:
        """Start SCHEDULED broadcasts whose time has passed (§18.1); the fan-out job sends their
        pages. Idempotent — a broadcast already started is never claimed again. Returns how many
        this run started."""
        started = 0
        for broadcast in await self._broadcast_repo.list_due_scheduled(Utils.datetime_now()):
            if await self._start(broadcast, [BroadcastStatus.SCHEDULED]) is not None:
                started += 1
        return started

    async def fanout_next_page(self) -> bool:
        """Send the next page of the broadcast that has waited longest. Whether anything moved:
        False when nothing is SENDING, or another runner took this page first."""
        broadcast = await self._broadcast_repo.oldest_sending()
        if broadcast is None:
            return False
        return await self._fanout_page(broadcast)

    async def run_scheduled_sweep(self, max_pages: Optional[int] = None) -> Dict[str, int]:
        """The admin trigger: start due scheduled broadcasts, then fan out up to *max_pages*."""
        started = await self.sweep_scheduled_broadcasts()
        limit = settings.BROADCAST_FANOUT_MAX_PAGES_PER_RUN if max_pages is None else max_pages
        pages = 0
        while pages < limit and await self.fanout_next_page():
            pages += 1
        return {"started": started, "pages": pages}

    # ── helpers ───────────────────────────────────────────────────

    async def _get(self, broadcast_id: str) -> Broadcast:
        broadcast = await self._broadcast_repo.get_model(broadcast_id)
        if broadcast is None:
            raise ResourceNotFoundException(resource="broadcast")
        return broadcast

    async def _count(self, audience: BroadcastAudience) -> int:
        user_type, persona = _AUDIENCE_FILTER[audience]
        return await self._users.count_recipients(user_type=user_type, persona=persona)

    async def _start(self, broadcast: Broadcast, from_statuses) -> Optional[Broadcast]:
        """Claim the broadcast for sending, once: a sweep and a "send now" (or two overlapping
        sweeps) cannot both start it. The claimed row, or None."""
        recipient_count = await self._count(BroadcastAudience(broadcast.audience))
        return await self._broadcast_repo.claim_transition(
            broadcast.id, from_statuses, BroadcastStatus.SENDING,
            recipient_count=recipient_count, recipients_enqueued=0, fanout_cursor=None,
        )

    async def _fanout_page(self, broadcast: Broadcast) -> bool:
        """Send the page after the broadcast's cursor; finish it when the audience runs out.

        The cursor advances with a claim pinned to the cursor this page was read from, before
        the event goes out, so a concurrent runner that read the same cursor loses the claim and
        sends nothing. Whether this call moved the broadcast.
        """
        page_size = settings.BROADCAST_FANOUT_PAGE_SIZE
        user_type, persona = _AUDIENCE_FILTER[BroadcastAudience(broadcast.audience)]
        recipients = await self._users.list_recipient_ids_page(
            broadcast.fanout_cursor, page_size, user_type=user_type, persona=persona,
        )
        last_page = len(recipients) < page_size
        values = {"fanout_cursor": recipients[-1]} if recipients else {}
        if last_page:
            values["sent_at"] = Utils.datetime_now()
        claimed = await self._broadcast_repo.claim_transition(
            broadcast.id, [BroadcastStatus.SENDING], BroadcastStatus.SENT if last_page else None,
            expect={"fanout_cursor": broadcast.fanout_cursor},
            increments={"recipients_enqueued": len(recipients)} if recipients else None,
            **values,
        )
        if claimed is None:
            return False
        if recipients:
            await publish_domain_event(DomainEvent(
                type=EventType.BROADCAST_ANNOUNCEMENT,
                recipient_user_ids=tuple(recipients),
                data={"subject": broadcast.subject, "body": broadcast.body},
            ))
        return True

    async def _fanout_page_in_savepoint(self, broadcast: Broadcast) -> None:
        """The first page, sent inside the request that started the broadcast. A failure rolls
        back this page alone and is logged; the broadcast stays SENDING at the same cursor, so
        the next tick sends the page instead."""
        try:
            async with get_db_session_from_context().begin_nested():
                await self._fanout_page(broadcast)
        except Exception as exc:  # noqa: BLE001 — the tick retries the page
            log_fault_once(exc, f"broadcast {broadcast.id}: inline fan-out page")

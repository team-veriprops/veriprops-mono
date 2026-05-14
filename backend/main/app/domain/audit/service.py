"""AuditLogService — R0.10 / S56.

Call .schedule() inside any @transactional service method to queue an audit write.
The write is executed atomically with the enclosing transaction by the @transactional
decorator's drain step (see appodus_utils/decorators/audit_ctx.py).

S56 adds read methods for admin audit export (R19.1), customer activity log (R19.2),
and agent task history (R19.3).
"""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from kink import inject

from main.app.domain.audit.models import (
    AdminActionLogPageDto,
    AuditActionType,
    AuditActivityPageDto,
    AuditEventDto,
    AuditPackRowDto,
    CreateAuditLogDto,
)
from main.app.domain.audit.repo import AuditLogRepo
from main.appodus_utils import Utils
from main.appodus_utils.decorators.audit_ctx import schedule_audit_write
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional

# Admin-mutation action types exposed via the action-log endpoint (R19.6)
ADMIN_ACTION_TYPES: List[str] = [
    AuditActionType.ADMIN_INVITED.value,
    AuditActionType.ADMIN_INVITE_ACCEPTED.value,
    AuditActionType.ADMIN_ROLE_CHANGED.value,
    AuditActionType.ADMIN_CONFIG_CHANGED.value,
    AuditActionType.AGENT_APPLICATION_APPROVED.value,
    AuditActionType.AGENT_APPLICATION_REJECTED.value,
    AuditActionType.WIRE_PROOF_CONFIRMED.value,
    AuditActionType.DATA_ERASURE_APPROVED.value,
    AuditActionType.DATA_ERASURE_EXECUTED.value,
    AuditActionType.DATA_ERASURE_REJECTED.value,
]


@inject
# schedule() is synchronous — exclude it from @transactional and method_trace_logger
# to avoid the async-only assertion in @transactional._wrapper.
@decorate_all_methods(transactional(), exclude=["schedule"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["schedule"], exclude_startswith=["_"])
class AuditLogService:
    def __init__(self, repo: AuditLogRepo):
        self._repo = repo

    def schedule(
        self,
        action: AuditActionType,
        resource_type: str,
        resource_id: str,
        *,
        actor_id: Optional[str] = None,
        from_state: Optional[str] = None,
        to_state: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        """Queue an audit write to run after the current @transactional flush."""
        dto = CreateAuditLogDto(
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            from_state=from_state,
            to_state=to_state,
            meta=meta,
            ip_address=ip_address,
            occurred_at=Utils.datetime_now(),
        )

        async def _write() -> None:
            await self._repo.create(dto)

        schedule_audit_write(_write)

    # ── S56 read methods ──────────────────────────────────────────────────────

    async def get_activity_log(
        self,
        resource_type: str,
        resource_id: str,
        page: int = 0,
        page_size: int = 20,
    ) -> AuditActivityPageDto:
        """PII-safe paginated event list for customer/agent views (no actor_id)."""
        rows, total = await self._repo.list_for_resource(
            resource_type=resource_type,
            resource_id=resource_id,
            offset=page * page_size,
            limit=page_size,
        )
        items = [
            AuditEventDto(
                action=r.action,
                occurred_at=r.occurred_at,
                from_state=r.from_state,
                to_state=r.to_state,
                meta=r.meta,
            )
            for r in rows
        ]
        return AuditActivityPageDto(items=items, total=total, page=page, page_size=page_size)

    async def export_verification_pack_csv(
        self,
        vid: str,
        task_ids: List[str],
    ) -> bytes:
        """Return a CSV byte string with the full audit trail for a verification."""
        rows = await self._repo.list_for_verification_pack(vid=vid, task_ids=task_ids)
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "occurred_at", "action", "actor_id", "resource_type", "resource_id",
            "from_state", "to_state", "ip_address", "meta",
        ])
        for r in rows:
            writer.writerow([
                r.occurred_at.isoformat() if r.occurred_at else "",
                r.action,
                r.actor_id or "",
                r.resource_type,
                r.resource_id,
                r.from_state or "",
                r.to_state or "",
                r.ip_address or "",
                json.dumps(r.meta) if r.meta else "",
            ])
        return buf.getvalue().encode("utf-8")

    async def list_admin_actions(
        self,
        action_types: Optional[List[str]] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        page: int = 0,
        page_size: int = 20,
    ) -> AdminActionLogPageDto:
        types = action_types if action_types else ADMIN_ACTION_TYPES
        rows, total = await self._repo.list_admin_actions(
            action_types=types,
            date_from=date_from,
            date_to=date_to,
            offset=page * page_size,
            limit=page_size,
        )
        items = [
            AuditPackRowDto(
                id=str(r.id),
                actor_id=r.actor_id,
                action=r.action,
                resource_type=r.resource_type,
                resource_id=r.resource_id,
                from_state=r.from_state,
                to_state=r.to_state,
                occurred_at=r.occurred_at,
                ip_address=r.ip_address,
                meta=r.meta,
            )
            for r in rows
        ]
        return AdminActionLogPageDto(items=items, total=total, page=page, page_size=page_size)

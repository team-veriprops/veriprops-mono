"""AuditLogService — R0.10.

Call .schedule() inside any @transactional service method to queue an audit write.
The write is executed atomically with the enclosing transaction by the @transactional
decorator's drain step (see appodus_utils/decorators/audit_ctx.py).
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from kink import inject

from main.app.domain.audit.models import AuditActionType, CreateAuditLogDto
from main.app.domain.audit.repo import AuditLogRepo
from main.appodus_utils import Utils
from main.appodus_utils.decorators.audit_ctx import schedule_audit_write
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional


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
        """Queue an audit write to run after the current @transactional flush.

        This method is synchronous and safe to call from anywhere inside a
        @transactional method. The actual INSERT happens in drain_audit_writes()
        which is invoked by the outermost @transactional decorator after flush().
        """
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

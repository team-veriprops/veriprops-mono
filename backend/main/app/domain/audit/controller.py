"""Audit log HTTP endpoints — S56 (R19.1, R19.6).

Admin-only routes:
  GET /admin/audit/verifications/{vid}/export   — full CSV audit pack for a verification
  GET /admin/audit/actions                       — filtered admin-mutation action log
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import Depends, Query
from fastapi.responses import StreamingResponse
from kink import di

from main.app.domain.audit.models import AdminActionLogPageDto
from main.app.domain.audit.service import AuditLogService
from main.app.domain.user.auth.utils.permissions import Permission, require_permission
from main.app.domain.verification.repo import VerificationRepo
from main.app.domain.verification.task.repo import TaskRepo
from main.appodus_utils.db.models import SuccessResponse
from main.appodus_utils.exception.exceptions import ResourceNotFoundException
from main.appodus_utils.router import AppRouter

audit_router = AppRouter(prefix="/admin/audit", tags=["Admin — Audit"])


@audit_router.get(
    "/verifications/{vid}/export",
    summary="Export full audit pack for a verification as CSV",
)
async def export_verification_audit(
    vid: str,
    _: str = Depends(require_permission(Permission.VIEW_ADMIN_PANEL)),
):
    svc: AuditLogService = di[AuditLogService]
    ver_repo: VerificationRepo = di[VerificationRepo]
    task_repo: TaskRepo = di[TaskRepo]
    verification = await ver_repo.get_by_vid(vid)
    if not verification:
        raise ResourceNotFoundException(resource=f"Verification {vid}")
    tasks = await task_repo.list_for_verification(str(verification.id))
    task_ids = [str(t.id) for t in tasks]
    csv_bytes = await svc.export_verification_pack_csv(vid=str(verification.id), task_ids=task_ids)

    def _stream():
        yield csv_bytes

    return StreamingResponse(
        _stream(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="audit-{vid}.csv"'},
    )


@audit_router.get(
    "/actions",
    response_model=SuccessResponse[AdminActionLogPageDto],
    summary="Paginated log of admin-mutation actions",
)
async def list_admin_actions(
    action_types: Optional[List[str]] = Query(default=None),
    date_from: Optional[datetime] = Query(default=None),
    date_to: Optional[datetime] = Query(default=None),
    page: int = Query(default=0, ge=0),
    page_size: int = Query(default=20, ge=1, le=100),
    _: str = Depends(require_permission(Permission.VIEW_ADMIN_PANEL)),
):
    svc: AuditLogService = di[AuditLogService]
    result = await svc.list_admin_actions(
        action_types=action_types,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    return SuccessResponse.ok(result)

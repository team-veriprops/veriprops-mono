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
from main.app.domain.audit.pack_service import VerificationAuditPackService
from main.app.domain.audit.service import AuditLogService
from main.app.domain.user.auth.utils.permissions import Permission, require_permission
from main.appodus_utils.db.models import SuccessResponse
from main.appodus_utils.router import AppRouter

audit_router = AppRouter(prefix="/admin/audit", tags=["Admin — Audit"])

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


@audit_router.get(
    "/verifications/{verification_id}/export",
    summary="Download the full CSV audit pack for a verification (§19.3)",
)
async def export_verification_pack(
    verification_id: str,
    _: str = Depends(require_permission(Permission.VIEW_ADMIN_PANEL)),
):
    pack: VerificationAuditPackService = di[VerificationAuditPackService]
    csv_bytes = await pack.build_pack_csv(verification_id)
    filename = f"veriprops-audit-pack-{verification_id}.csv"
    return StreamingResponse(
        iter([csv_bytes]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

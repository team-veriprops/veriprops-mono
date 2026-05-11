"""Conflict flag HTTP routes — admin list + resolve (S29).

URL shape: /api/admin/verifications/{vid}/conflicts/...
All endpoints require MANAGE_VERIFICATIONS permission.
"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from kink import di

from main.app.domain.user.auth.utils.permissions import Permission, require_permission
from main.app.domain.verification.conflict.models import (
    ConflictFlagDto,
    ResolveConflictDto,
)
from main.app.domain.verification.conflict.service import ConflictService
from main.appodus_utils.db.models import SuccessResponse

conflict_service: ConflictService = di[ConflictService]

conflict_router = APIRouter(
    prefix="/admin/verifications",
    tags=["Admin - Conflict Flags"],
)


@conflict_router.get(
    "/{vid}/conflicts",
    response_model=SuccessResponse[List[ConflictFlagDto]],
)
async def list_conflicts(
    vid: str,
    _: str = Depends(require_permission(Permission.MANAGE_VERIFICATIONS)),
):
    flags = await conflict_service.list_for_verification(vid)
    return SuccessResponse[List[ConflictFlagDto]](data=flags)


@conflict_router.post(
    "/{vid}/conflicts/{conflict_id}/resolve",
    response_model=SuccessResponse[ConflictFlagDto],
)
async def resolve_conflict(
    vid: str,
    conflict_id: str,
    req: ResolveConflictDto,
    admin_id: str = Depends(require_permission(Permission.MANAGE_VERIFICATIONS)),
):
    flag = await conflict_service.resolve(conflict_id, admin_id, req)
    return SuccessResponse[ConflictFlagDto](data=flag)

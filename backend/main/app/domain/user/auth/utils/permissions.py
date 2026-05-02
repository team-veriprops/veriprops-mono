"""RBAC permissions — PRD §4.1.

Permission enum + role-to-permission matrix + a FastAPI dependency that
extracts the authenticated user's claims and asserts a permission.

Usage:
    from main.app.domain.user.auth.utils.permissions import (
        Permission, require_permission,
    )

    @router.post("/admin/foo", dependencies=[Depends(require_permission(Permission.APPROVE_AGENT))])
    async def foo(): ...
"""
from __future__ import annotations

import enum
from typing import Callable, Set

from fastapi import Depends
from libre_fastapi_jwt import AuthJWT

from main.app.domain.user.auth.session.models import UserType
from main.app.domain.user.models import AdminSubRole
from main.appodus_utils.exception.exceptions import ForbiddenException


class Permission(str, enum.Enum):
    INVITE_ADMIN = "INVITE_ADMIN"
    APPROVE_AGENT = "APPROVE_AGENT"
    ASSIGN_AGENT = "ASSIGN_AGENT"
    APPROVE_PAYOUT = "APPROVE_PAYOUT"
    CONFIGURE_PRICING = "CONFIGURE_PRICING"
    RESOLVE_DISPUTE = "RESOLVE_DISPUTE"
    RELEASE_REPORT = "RELEASE_REPORT"
    CONFIRM_WIRE_PAYMENT = "CONFIRM_WIRE_PAYMENT"
    VIEW_ADMIN_PANEL = "VIEW_ADMIN_PANEL"


# Role → permissions matrix. Super admins implicitly hold every permission.
_ROLE_MATRIX: dict[AdminSubRole, Set[Permission]] = {
    AdminSubRole.SUPER: set(Permission),
    AdminSubRole.OPERATIONS: {
        Permission.APPROVE_AGENT,
        Permission.ASSIGN_AGENT,
        Permission.RESOLVE_DISPUTE,
        Permission.RELEASE_REPORT,
        Permission.VIEW_ADMIN_PANEL,
    },
    AdminSubRole.FINANCE: {
        Permission.APPROVE_PAYOUT,
        Permission.CONFIGURE_PRICING,
        Permission.CONFIRM_WIRE_PAYMENT,
        Permission.VIEW_ADMIN_PANEL,
    },
}


def has_permission(user_type: str | None, sub_role: str | None, permission: Permission) -> bool:
    if (user_type or "").upper() != UserType.ADMIN.value:
        return False
    if not sub_role:
        return False
    try:
        role = AdminSubRole(sub_role)
    except ValueError:
        return False
    return permission in _ROLE_MATRIX.get(role, set())


def require_permission(permission: Permission) -> Callable:
    """FastAPI dependency factory."""

    async def _dep(authorize: AuthJWT = Depends()) -> str:
        authorize.jwt_required()
        claims = authorize.get_raw_jwt() or {}
        user_type = claims.get("user_type")
        sub_role = claims.get("admin_sub_role")
        if not has_permission(user_type, sub_role, permission):
            raise ForbiddenException(message=f"Missing permission: {permission.value}")
        return authorize.get_jwt_subject()

    return _dep


async def require_admin(authorize: AuthJWT = Depends()) -> str:
    """Lightweight 'any admin' guard — short-circuits before more specific checks."""
    authorize.jwt_required()
    claims = authorize.get_raw_jwt() or {}
    user_type = (claims.get("user_type") or "").upper()
    if user_type != UserType.ADMIN.value:
        raise ForbiddenException(message="Admin access required")
    return authorize.get_jwt_subject()

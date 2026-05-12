"""JWT auth dependency — AuthJWTBearer wraps libre_fastapi_jwt AuthJWT."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from fastapi import Depends
from libre_fastapi_jwt import AuthJWT

from main.appodus_utils.exception.exceptions import ForbiddenException


@dataclass
class JWTClaims:
    sub: str
    user_type: str
    admin_sub_role: Optional[str] = None
    raw: Optional[dict] = field(default=None, repr=False)


async def _extract_claims(authorize: AuthJWT = Depends()) -> JWTClaims:
    authorize.jwt_required()
    raw = authorize.get_raw_jwt() or {}
    sub = authorize.get_jwt_subject()
    if not sub:
        raise ForbiddenException(message="Invalid token: missing subject")
    return JWTClaims(
        sub=sub,
        user_type=raw.get("user_type", ""),
        admin_sub_role=raw.get("admin_sub_role"),
        raw=raw,
    )


class AuthJWTBearer:
    """FastAPI callable dependency that validates the JWT cookie and returns JWTClaims.

    Usage:
        _auth = AuthJWTBearer()
        claims = Depends(_auth)   ->  JWTClaims

        _admin_auth = AuthJWTBearer(required_permissions=["MANAGE_VERIFICATIONS"])
    """

    def __init__(self, required_permissions: Optional[List[str]] = None):
        self._required_permissions = required_permissions or []

    async def __call__(self, claims: JWTClaims = Depends(_extract_claims)) -> JWTClaims:
        if self._required_permissions:
            from main.app.domain.user.auth.utils.permissions import has_permission, Permission
            for perm_name in self._required_permissions:
                try:
                    perm = Permission(perm_name)
                except ValueError:
                    continue
                if has_permission(claims.user_type, claims.admin_sub_role, perm):
                    break
            else:
                raise ForbiddenException(
                    message=f"Missing required permission(s): {self._required_permissions}"
                )
        return claims

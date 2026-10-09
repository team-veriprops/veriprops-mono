"""Every mounted route is either deliberately public or refuses a caller it doesn't serve (§4, §6a).

Table-driven off the live route table, so a new route is covered the day it is mounted:

- **No session.** Each route outside `PUBLIC` answers 401. A route that validates its request
  before authenticating answers 422 first; for those, the proof is static instead — the first
  thing its handler awaits is the session check, so no work happens for an anonymous caller.
- **Wrong persona.** Every admin route refuses a customer's session with 403, and every route
  guarded by a permission refuses each admin sub-role that lacks it — both decided from the
  token's claims alone, before any data is read.

The app under test carries the real routes and exception handlers without the middleware stack,
so no database is needed: a refusal must happen before anything touches one.
"""
import ast
import inspect
import re
import textwrap
from typing import Iterator, Optional, Tuple

import jwt
import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from libre_fastapi_jwt import AuthJWT

from main.app.config.settings import settings
from main.app.domain.user.auth.session.models import UserPersona, UserType
from main.app.domain.user.auth.utils.permissions import Permission, has_permission
from main.app.domain.user.models import AdminSubRole
from veriprops import app as real_app

_ID = "00000000-0000-0000-0000-000000000001"

# (method, path) → why it needs no session. Anything else must refuse an anonymous caller.
PUBLIC = {
    ("GET", "/health"): "liveness probe",
    ("GET", "/api/config/public"): "public config the website renders",
    ("GET", "/api/config/nigeria-locations"): "the states canon (§16.1)",
    ("GET", "/api/public/verify/{vid}"): "public VID lookup (§13)",
    ("GET", "/api/public/shared/{token}"): "share link, authorised by its token (§13)",
    ("POST", "/api/public/shared/{token}/acknowledge"): "share link, authorised by its token (§13)",
    ("POST", "/api/public/wa/handoff/{intent}/{token}/redeem"): "WhatsApp handoff link, authorised by its token (§26.5)",
    ("PUT", "/api/public/wa/handoff/pay/consent"): "handoff grant cookie (§26.5)",
    ("POST", "/api/public/wa/handoff/pay/initiate"): "handoff grant cookie (§26.5)",
    ("POST", "/api/public/wa/handoff/pay/reconcile"): "handoff grant cookie (§26.5)",
    ("POST", "/api/public/wa/handoff/release"): "drops the caller's own grant cookie",
    ("GET", "/api/users/auth/consents/documents"): "legal documents are public",
    ("GET", "/api/users/auth/consents/documents/{slug}"): "legal documents are public",
    ("GET", "/api/users/admins/invitations/preview/{token}"): "admin invite, authorised by its token",
    ("POST", "/api/users/admins/invitations/accept"): "admin invite, authorised by its token",
    ("GET", "/api/users/auth/oauth/{provider}/start"): "social sign-in",
    ("GET", "/api/users/auth/oauth/{provider}/callback"): "social sign-in",
    ("POST", "/api/users/auth/oauth/{provider}/callback"): "social sign-in",
    ("POST", "/api/users/auth/sessions"): "sign-in",
    ("POST", "/api/users/auth/sessions/current"): "refresh, authorised by the refresh cookie",
    ("DELETE", "/api/users/auth/sessions/current"): "sign-out must clear cookies even without a session",
    ("POST", "/api/users/auth/signup"): "signup",
    ("POST", "/api/users/auth/otp/send"): "OTP for signup / sign-in",
    ("POST", "/api/users/auth/otp/verify"): "OTP for signup / sign-in",
    ("POST", "/api/users/auth/password/forgot"): "password recovery",
    ("POST", "/api/users/auth/password/reset"): "password recovery, authorised by its token",
    ("GET", "/api/verifications/quote"): "price quote on the public pricing page",
    ("GET", "/api/webhooks/{platform}/redirect"): "gateway redirect",
    ("GET", "/api/webhooks/{platform}"): "provider webhook, signature-verified",
    ("POST", "/api/webhooks/{platform}"): "provider webhook, signature-verified",
    ("POST", "/api/payments/stub/confirm"): "stub checkout, 404 unless PAYMENT_STUB_MODE",
    ("POST", "/api/payments/chargebacks/stub/flag"): "stub gateway, 404 unless PAYMENT_STUB_MODE",
    ("POST", "/api/internal/sweeps/tick"): "Cloudflare Cron, authorised by SWEEP_TRIGGER_SECRET; 404 unless set",
}
# Dev doors are unmounted in production and 404 there too (CLAUDE.md "Dev endpoints").
_DEV_PREFIX = "/api/dev/"
# Server-sent event streams hold the connection open; their handlers authenticate first (static check).
_STREAMS = {("GET", "/api/verifications/{verification_id}/stream"), ("GET", "/api/chat/stream")}


def _test_app() -> FastAPI:
    app = FastAPI(exception_handlers=real_app.exception_handlers)
    app.router.routes.extend(real_app.router.routes)
    return app


_CLIENT = TestClient(_test_app(), raise_server_exceptions=False)


def _routes() -> Iterator[Tuple[str, APIRoute]]:
    for route in real_app.routes:
        if isinstance(route, APIRoute):
            for method in sorted(route.methods - {"HEAD"}):
                yield method, route


def _is_public(method: str, route: APIRoute) -> bool:
    return (method, route.path) in PUBLIC or route.path.startswith(_DEV_PREFIX)


def _call(method: str, route: APIRoute, headers: Optional[dict] = None):
    path = re.sub(r"\{[^}]+\}", _ID, route.path)
    body = {} if method in ("POST", "PUT", "PATCH") else None
    return _CLIENT.request(method, path, json=body, headers=headers or {})


_GUARD_CALLS = {"jwt_required", "require_admin"}


def _authenticates_first(route: APIRoute) -> bool:
    """Whether the handler's first awaited call is the session check (or a dependency guard
    already ran it)."""
    if _guard_permission(route) is not None or _has_dependency(route, "require_admin"):
        return True
    source = textwrap.dedent(inspect.getsource(route.endpoint))
    fn = ast.parse(source).body[0]
    for node in ast.walk(fn):
        if isinstance(node, ast.Await) and isinstance(node.value, ast.Call):
            called = node.value.func
            name = called.attr if isinstance(called, ast.Attribute) else getattr(called, "id", "")
            return name in _GUARD_CALLS
    return False


def _dependencies(route: APIRoute):
    stack = list(route.dependant.dependencies)
    while stack:
        dep = stack.pop()
        yield dep
        stack.extend(dep.dependencies)


def _has_dependency(route: APIRoute, name: str) -> bool:
    return any(getattr(dep.call, "__name__", "") == name for dep in _dependencies(route))


def _guard_permission(route: APIRoute) -> Optional[Permission]:
    """The permission a `require_permission(...)` dependency on this route demands, if any."""
    for dep in _dependencies(route):
        call = dep.call
        if getattr(call, "__qualname__", "") == "require_permission.<locals>._dep":
            for cell in call.__closure__ or ():
                if isinstance(cell.cell_contents, Permission):
                    return cell.cell_contents
    return None


def _session(user_type: UserType, *, sub_role: Optional[AdminSubRole] = None, personas=()) -> dict:
    """Headers carrying a signed access cookie (and its CSRF double-submit) for these claims."""
    token = AuthJWT().create_access_token(subject=_ID, user_claims={
        "user_type": user_type.value,
        "personas": [p.value for p in personas],
        "admin_sub_role": sub_role.value if sub_role else None,
    })
    csrf = jwt.decode(token, options={"verify_signature": False}).get("csrf", "")
    return {"Cookie": f"{settings.AUTHJWT_ACCESS_COOKIE_KEY}={token}", "X-CSRF-Token": csrf}


@pytest.fixture(autouse=True)
def never_revoked(monkeypatch):
    """The denylist lives in Redis; a freshly minted token was never revoked."""
    async def _never(_token):
        return False
    monkeypatch.setattr(AuthJWT, "_token_in_denylist_callback", _never)


# ── no session ────────────────────────────────────────────────────────────────

_PROTECTED = [(m, r) for m, r in _routes() if not _is_public(m, r)]


@pytest.mark.parametrize("method, route", _PROTECTED, ids=[f"{m} {r.path}" for m, r in _PROTECTED])
def test_a_protected_route_refuses_a_caller_without_a_session(method, route):
    if (method, route.path) in _STREAMS:
        assert _authenticates_first(route)
        return
    status = _call(method, route).status_code
    if status == 422:
        assert _authenticates_first(route), "validates its request before authenticating, and its handler does not authenticate first"
        return
    assert status == 401


def test_every_public_entry_is_a_mounted_route():
    mounted = {(m, r.path) for m, r in _routes()}
    assert not set(PUBLIC) - mounted, f"stale PUBLIC entries: {sorted(set(PUBLIC) - mounted)}"


# ── wrong persona ─────────────────────────────────────────────────────────────

_ADMIN = [(m, r) for m, r in _routes() if r.path.startswith("/api/admin/")]


@pytest.mark.parametrize("method, route", _ADMIN, ids=[f"{m} {r.path}" for m, r in _ADMIN])
def test_an_admin_route_refuses_a_customer(method, route):
    customer = _session(UserType.USER, personas=[UserPersona.CUSTOMER])

    assert _call(method, route, customer).status_code == 403


_GUARDED = [
    (m, r, role, perm)
    for m, r in _routes()
    if (perm := _guard_permission(r)) is not None
    for role in AdminSubRole
    if not has_permission(UserType.ADMIN.value, role.value, perm)
]


@pytest.mark.parametrize(
    "method, route, role, permission", _GUARDED,
    ids=[f"{role.value} {m} {r.path}" for m, r, role, _ in _GUARDED],
)
def test_a_permission_guarded_route_refuses_a_sub_role_without_that_permission(method, route, role, permission):
    admin = _session(UserType.ADMIN, sub_role=role)

    assert _call(method, route, admin).status_code == 403


def test_the_matrix_is_exercised():
    """Guards the guard: the route table really has permission-guarded admin routes to check."""
    assert len(_ADMIN) > 50 and len(_GUARDED) > 100

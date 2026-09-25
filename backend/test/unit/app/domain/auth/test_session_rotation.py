"""Unit tests for in-place session rotation (§3.2 persona grants).

A persona is granted server-side — AGENT when an application is submitted, CUSTOMER when an agent
takes up the customer hat — but the caller's tokens still carry the personas they were minted with,
and the frontend route guard reads the *refresh* token. Refreshing re-mints only the access token,
so without rotation a freshly granted persona cannot open its own area until the next sign-in.

Rotation re-mints both tokens and moves the device-session row onto the new refresh hash, which is
the step that keeps the row from being orphaned: the row is keyed by that hash, and a session whose
row no longer matches is treated as revoked on the next refresh.
"""
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.domain.user.auth.session.models import UpdateDeviceSessionDto
from main.appodus_utils.db.session import db_session_ctx


@pytest.fixture(autouse=True)
def mock_db_session():
    session = MagicMock()
    session.in_transaction.return_value = False

    @asynccontextmanager
    async def _begin():
        yield

    session.begin = _begin
    session.flush = AsyncMock()
    session.execute = AsyncMock()  # the per-user device-session advisory lock
    token = db_session_ctx.set(session)
    yield session
    db_session_ctx.reset(token)


def _make_user(personas):
    return SimpleNamespace(
        id="u-1",
        user_type="USER",
        personas=personas,
        admin_sub_role=None,
    )


def _make_service(monkeypatch, *, device=None, new_hash="new-hash"):
    """A SessionService with its collaborators mocked and token minting captured."""
    from main.app.domain.user.auth.session import service as service_module

    svc = object.__new__(service_module.SessionService)
    svc._device_repo = AsyncMock()
    svc._event_repo = AsyncMock()
    svc._reset_repo = AsyncMock()
    svc._device_repo.get_by_token_hash = AsyncMock(return_value=device)
    svc._device_repo.update = AsyncMock()

    mint = MagicMock(return_value=new_hash)
    monkeypatch.setattr(service_module.JwtAuthUtils, "set_access_token", mint)

    session_dto = object()
    svc.build_session_dto = AsyncMock(return_value=session_dto)
    return svc, mint, session_dto


def _device_row(row_id="d-1", token_hash="old-hash"):
    return SimpleNamespace(id=row_id, refresh_token_hash=token_hash)


async def test_rotation_mints_both_tokens_from_the_current_personas(monkeypatch):
    """The whole point: the new tokens say what the user record says *now*."""
    svc, mint, session_dto = _make_service(monkeypatch, device=_device_row())
    user = _make_user(["CUSTOMER", "AGENT"])
    authorize = MagicMock()

    result = await svc.rotate_current_session(user, authorize, "old-hash")

    mint.assert_called_once()
    assert mint.call_args.kwargs["user_personas"] == ["CUSTOMER", "AGENT"]
    assert mint.call_args.kwargs["user_id"] == "u-1"
    assert mint.call_args.kwargs["authorize"] is authorize
    assert result is session_dto


async def test_the_device_row_follows_the_new_refresh_hash(monkeypatch):
    """The row is keyed by the refresh hash — left behind, it is a revoked session."""
    svc, _, _ = _make_service(monkeypatch, device=_device_row(), new_hash="rotated-hash")

    await svc.rotate_current_session(_make_user(["CUSTOMER"]), MagicMock(), "old-hash")

    svc._device_repo.update.assert_awaited_once()
    session_id, dto = svc._device_repo.update.await_args[0]
    assert session_id == "d-1"
    assert isinstance(dto, UpdateDeviceSessionDto)
    assert dto.refresh_token_hash == "rotated-hash"
    assert dto.last_active_at is not None


async def test_a_revoked_or_absent_session_is_not_resurrected(monkeypatch):
    """`get_by_token_hash` already excludes revoked rows, so a miss means the session is over.

    Minting anyway would hand the caller a refresh cookie no row backs — a session that looks live
    until its next refresh. Their existing cookies are already dead, so the next refresh signs them
    out and the grant takes effect when they sign back in.
    """
    svc, mint, session_dto = _make_service(monkeypatch, device=None)

    result = await svc.rotate_current_session(_make_user(["CUSTOMER"]), MagicMock(), "old-hash")

    mint.assert_not_called()
    svc._device_repo.update.assert_not_awaited()
    assert result is session_dto


async def test_no_current_token_hash_is_the_same_as_no_session(monkeypatch):
    """A caller with no refresh cookie has nothing to rotate."""
    svc, mint, _ = _make_service(monkeypatch, device=_device_row())

    await svc.rotate_current_session(_make_user(["CUSTOMER"]), MagicMock(), None)

    mint.assert_not_called()
    svc._device_repo.get_by_token_hash.assert_not_awaited()

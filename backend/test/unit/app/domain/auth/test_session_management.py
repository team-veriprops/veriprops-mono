"""Unit tests for connected-device session management (R2.8).

Verifies:
- list_devices() returns sessions for the correct user.
- revoke_device() marks the targeted session revoked.
- revoke_all_other_devices() skips the current session.
- revoke_all_devices_for_user() revokes every session (used on password reset).
"""
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.appodus_utils.db.session import db_session_ctx
from main.app.domain.user.auth.session.models import UpdateDeviceSessionDto


@pytest.fixture(autouse=True)
def mock_db_session():
    session = MagicMock()
    session.in_transaction.return_value = False

    @asynccontextmanager
    async def _begin():
        yield

    session.begin = _begin
    session.flush = AsyncMock()
    token = db_session_ctx.set(session)
    yield session
    db_session_ctx.reset(token)


def _make_device_session(session_id: str, user_id: str, token_hash: str):
    s = MagicMock()
    s.id = session_id
    s.user_id = user_id
    s.refresh_token_hash = token_hash
    s.revoked = False
    return s


def _make_service():
    from main.app.domain.user.auth.session.service import SessionService
    svc = object.__new__(SessionService)
    svc._device_repo = AsyncMock()
    svc._event_repo = AsyncMock()
    svc._reset_repo = AsyncMock()
    return svc


# ── list_devices ─────────────────────────────────────────────────────────────

async def test_list_devices_delegates_to_repo():
    sessions = [_make_device_session("s1", "u1", "hash1")]
    svc = _make_service()
    svc._device_repo.list_for_user = AsyncMock(return_value=sessions)

    result = await svc.list_devices("u1")

    svc._device_repo.list_for_user.assert_called_once_with("u1")
    assert result == sessions


# ── revoke_device ────────────────────────────────────────────────────────────

async def test_revoke_device_marks_session_revoked():
    svc = _make_service()
    svc._device_repo.update = AsyncMock()

    await svc.revoke_device("sess-abc")

    svc._device_repo.update.assert_called_once()
    session_id, dto = svc._device_repo.update.call_args[0]
    assert session_id == "sess-abc"
    assert isinstance(dto, UpdateDeviceSessionDto)
    assert dto.revoked is True
    assert dto.revoked_at is not None


# ── revoke_all_other_devices ─────────────────────────────────────────────────

async def test_revoke_all_other_devices_skips_current_session():
    current_hash = "current-token-hash"
    sessions = [
        _make_device_session("s1", "u1", current_hash),
        _make_device_session("s2", "u1", "other-hash-1"),
        _make_device_session("s3", "u1", "other-hash-2"),
    ]
    svc = _make_service()
    svc._device_repo.list_for_user = AsyncMock(return_value=sessions)
    svc._device_repo.update = AsyncMock()

    revoked_count = await svc.revoke_all_other_devices("u1", current_hash)

    assert revoked_count == 2
    updated_ids = [c[0][0] for c in svc._device_repo.update.call_args_list]
    assert "s1" not in updated_ids
    assert "s2" in updated_ids
    assert "s3" in updated_ids


async def test_revoke_all_other_devices_returns_zero_when_only_current():
    current_hash = "only-session-hash"
    sessions = [_make_device_session("s1", "u1", current_hash)]
    svc = _make_service()
    svc._device_repo.list_for_user = AsyncMock(return_value=sessions)
    svc._device_repo.update = AsyncMock()

    revoked_count = await svc.revoke_all_other_devices("u1", current_hash)

    assert revoked_count == 0
    svc._device_repo.update.assert_not_called()


# ── revoke_all_devices_for_user ──────────────────────────────────────────────

async def test_revoke_all_devices_for_user_revokes_every_session():
    """Password reset path — no session is spared."""
    sessions = [
        _make_device_session("s1", "u1", "hash1"),
        _make_device_session("s2", "u1", "hash2"),
    ]
    svc = _make_service()
    svc._device_repo.list_for_user = AsyncMock(return_value=sessions)
    svc._device_repo.update = AsyncMock()

    revoked_count = await svc.revoke_all_devices_for_user("u1")

    assert revoked_count == 2
    updated_ids = {c[0][0] for c in svc._device_repo.update.call_args_list}
    assert updated_ids == {"s1", "s2"}

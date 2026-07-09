"""Unit tests for forgot-password / reset-password flows (R2.5).

Verifies:
- request_password_reset() never reveals whether an email exists.
- reset_password() rejects expired tokens (1-hr TTL).
- reset_password() rejects already-consumed tokens (single-use).
- reset_password() revokes all sessions on success.
- reset_password() emits PASSWORD_CHANGED security event.
"""
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.appodus_utils.db.session import db_session_ctx


# ── Session fixture ──────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def mock_db_session():
    """Provide a fake AsyncSession so @transactional(USE_IF_PRESENT) doesn't raise."""
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


# ── Helpers ─────────────────────────────────────────────────────────────────

def _make_user(user_id: str = "uid-1"):
    user = MagicMock()
    user.id = user_id
    user.first_name = "Ada"
    user.last_name = "Williams"
    user.email = "ada@example.com"
    user.password_hash = "hashed"
    return user


def _make_token(user_id: str = "uid-1", expired: bool = False):
    from datetime import timedelta
    token = MagicMock()
    token.id = "tok-1"
    token.user_id = user_id
    if expired:
        token.expires_at = datetime.now(timezone.utc) - timedelta(hours=2)
    else:
        token.expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    token.consumed_at = None
    return token


def _make_service(**overrides):
    from main.app.domain.user.auth.service import AuthService
    svc = object.__new__(AuthService)
    svc._user_service = overrides.get("user_service", AsyncMock())
    svc._consent_service = overrides.get("consent_service", AsyncMock())
    svc._session_service = overrides.get("session_service", AsyncMock())
    svc._otp_service = overrides.get("otp_service", AsyncMock())
    svc._oauth_identity_service = overrides.get("oauth_identity_service", AsyncMock())
    return svc


# ── request_password_reset ───────────────────────────────────────────────────

async def test_forgot_returns_none_for_unknown_email():
    """Never disclose whether the email exists."""
    svc = _make_service()
    svc._user_service.get_user_by_email = AsyncMock(return_value=None)

    result = await svc.request_password_reset("unknown@example.com")

    assert result is None
    svc._session_service.create_password_reset_token.assert_not_called()


async def test_forgot_returns_token_tuple_for_known_email():
    user = _make_user()
    svc = _make_service()
    svc._user_service.get_user_by_email = AsyncMock(return_value=user)
    svc._session_service.create_password_reset_token = AsyncMock()
    svc._session_service.record_event = AsyncMock()

    result = await svc.request_password_reset("ada@example.com")

    assert result is not None
    raw_token, fullname = result
    assert isinstance(raw_token, str) and len(raw_token) == 36
    assert "Ada" in fullname


async def test_forgot_stores_token_hash_not_plaintext():
    user = _make_user()
    svc = _make_service()
    svc._user_service.get_user_by_email = AsyncMock(return_value=user)
    svc._session_service.create_password_reset_token = AsyncMock()
    svc._session_service.record_event = AsyncMock()

    result = await svc.request_password_reset("ada@example.com")
    raw_token, _ = result

    call_kwargs = svc._session_service.create_password_reset_token.call_args.kwargs
    stored_hash = call_kwargs["token_hash"]
    # Hash is a 64-char SHA-256 hex digest, never the raw token
    assert len(stored_hash) == 64
    assert stored_hash != raw_token


async def test_forgot_emits_password_reset_requested_event():
    from main.app.domain.user.auth.session.models import SecurityEventType
    user = _make_user()
    svc = _make_service()
    svc._user_service.get_user_by_email = AsyncMock(return_value=user)
    svc._session_service.create_password_reset_token = AsyncMock()
    svc._session_service.record_event = AsyncMock()

    await svc.request_password_reset("ada@example.com")

    svc._session_service.record_event.assert_called_once()
    event_type = svc._session_service.record_event.call_args[0][0]
    assert event_type == SecurityEventType.PASSWORD_RESET_REQUESTED


# ── reset_password ───────────────────────────────────────────────────────────

async def test_reset_rejects_invalid_or_expired_token():
    from main.appodus_utils.exception.exceptions import InvalidTokenException
    svc = _make_service()
    svc._session_service.consume_password_reset_token = AsyncMock(return_value=None)

    with pytest.raises(InvalidTokenException):
        await svc.reset_password("bad-token", "NewP4ss!word")


async def test_reset_rejects_weak_password():
    from main.appodus_utils.exception.exceptions import ValidationException
    token = _make_token()
    svc = _make_service()
    svc._session_service.consume_password_reset_token = AsyncMock(return_value=token)

    with pytest.raises(ValidationException):
        await svc.reset_password("good-token", "short")


async def test_reset_revokes_all_sessions_on_success():
    token = _make_token()
    user = _make_user()
    svc = _make_service()
    svc._session_service.consume_password_reset_token = AsyncMock(return_value=token)
    svc._user_service.set_password_hash = AsyncMock()
    svc._session_service.revoke_all_devices_for_user = AsyncMock()
    svc._session_service.record_event = AsyncMock()
    svc._user_service.get_user_model = AsyncMock(return_value=user)

    await svc.reset_password("valid-token", "NewP4ss!word")

    svc._session_service.revoke_all_devices_for_user.assert_called_once_with("uid-1")


async def test_reset_emits_password_changed_event():
    from main.app.domain.user.auth.session.models import SecurityEventType
    token = _make_token()
    user = _make_user()
    svc = _make_service()
    svc._session_service.consume_password_reset_token = AsyncMock(return_value=token)
    svc._user_service.set_password_hash = AsyncMock()
    svc._session_service.revoke_all_devices_for_user = AsyncMock()
    svc._session_service.record_event = AsyncMock()
    svc._user_service.get_user_model = AsyncMock(return_value=user)

    await svc.reset_password("valid-token", "NewP4ss!word")

    event_type = svc._session_service.record_event.call_args[0][0]
    assert event_type == SecurityEventType.PASSWORD_CHANGED


async def test_reset_password_hash_never_stored_as_plaintext():
    token = _make_token()
    user = _make_user()
    plain = "NewP4ss!word"
    svc = _make_service()
    svc._session_service.consume_password_reset_token = AsyncMock(return_value=token)
    svc._user_service.set_password_hash = AsyncMock()
    svc._session_service.revoke_all_devices_for_user = AsyncMock()
    svc._session_service.record_event = AsyncMock()
    svc._user_service.get_user_model = AsyncMock(return_value=user)

    await svc.reset_password("valid-token", plain)

    stored = svc._user_service.set_password_hash.call_args[0][1]
    assert stored != plain
    assert len(stored) > 20

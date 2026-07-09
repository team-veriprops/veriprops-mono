"""Unit tests for linked OAuth account management (R2.9).

Verifies:
- unlink_oauth() succeeds when the user has a password set.
- unlink_oauth() raises when the user has no password (guard).
- link_oauth_to_authenticated_user() attaches provider + emits OAUTH_LINKED.
- find_or_create_oauth_user() raises on email collision with a password account.
"""
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.appodus_utils.db.session import db_session_ctx
from main.app.domain.user.auth.oauth.providers.models import SocialAuthProvider
from main.app.domain.user.auth.session.models import SecurityEventType, UserPersona
from main.appodus_utils.exception.exceptions import ValidationException, UserAlreadyExistsException


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


def _make_user(user_id: str = "uid-1", has_password: bool = True):
    user = MagicMock()
    user.id = user_id
    user.first_name = "Ada"
    user.email = "ada@example.com"
    user.password_hash = "hashed" if has_password else None
    user.personas = [UserPersona.CUSTOMER]
    return user


def _make_service(**overrides):
    from main.app.domain.user.auth.service import AuthService
    svc = object.__new__(AuthService)
    svc._user_service = overrides.get("user_service", AsyncMock())
    svc._consent_service = overrides.get("consent_service", AsyncMock())
    svc._session_service = overrides.get("session_service", AsyncMock())
    svc._otp_service = overrides.get("otp_service", AsyncMock())
    svc._oauth_identity_service = overrides.get("oauth_identity_service", AsyncMock())
    return svc


# ── unlink_oauth ─────────────────────────────────────────────────────────────

async def test_unlink_succeeds_when_user_has_password():
    user = _make_user(has_password=True)
    svc = _make_service()
    svc._user_service.get_user_model = AsyncMock(return_value=user)
    svc._oauth_identity_service.unlink_oauth = AsyncMock()
    svc._session_service.record_event = AsyncMock()

    await svc.unlink_oauth("uid-1", SocialAuthProvider.GOOGLE)

    svc._oauth_identity_service.unlink_oauth.assert_called_once_with("uid-1", SocialAuthProvider.GOOGLE)


async def test_unlink_emits_oauth_unlinked_event():
    user = _make_user(has_password=True)
    svc = _make_service()
    svc._user_service.get_user_model = AsyncMock(return_value=user)
    svc._oauth_identity_service.unlink_oauth = AsyncMock()
    svc._session_service.record_event = AsyncMock()

    await svc.unlink_oauth("uid-1", SocialAuthProvider.GOOGLE)

    event_type = svc._session_service.record_event.call_args[0][0]
    assert event_type == SecurityEventType.OAUTH_UNLINKED


async def test_unlink_raises_when_user_has_no_password():
    """Cannot unlink the last sign-in method without a fallback password."""
    user = _make_user(has_password=False)
    svc = _make_service()
    svc._user_service.get_user_model = AsyncMock(return_value=user)

    with pytest.raises(ValidationException, match="Set a password"):
        await svc.unlink_oauth("uid-1", SocialAuthProvider.GOOGLE)

    svc._oauth_identity_service.unlink_oauth.assert_not_called()


# ── link_oauth_to_authenticated_user ─────────────────────────────────────────

async def test_link_oauth_attaches_provider():
    svc = _make_service()
    svc._oauth_identity_service.link_oauth = AsyncMock()
    svc._session_service.record_event = AsyncMock()

    await svc.link_oauth_to_authenticated_user(
        user_id="uid-1",
        provider=SocialAuthProvider.GOOGLE,
        subject="google-sub-123",
        email="ada@example.com",
        raw_profile={"name": "Ada"},
    )

    svc._oauth_identity_service.link_oauth.assert_called_once()
    args = svc._oauth_identity_service.link_oauth.call_args[0]
    assert args[0] == "uid-1"
    assert args[1] == SocialAuthProvider.GOOGLE
    assert args[2] == "google-sub-123"


async def test_link_oauth_emits_linked_event():
    svc = _make_service()
    svc._oauth_identity_service.link_oauth = AsyncMock()
    svc._session_service.record_event = AsyncMock()

    await svc.link_oauth_to_authenticated_user(
        user_id="uid-1",
        provider=SocialAuthProvider.FACEBOOK,
        subject="fb-456",
        email="ada@example.com",
        raw_profile={},
    )

    event_type = svc._session_service.record_event.call_args[0][0]
    assert event_type == SecurityEventType.OAUTH_LINKED


# ── find_or_create_oauth_user — email collision ───────────────────────────────

async def test_email_collision_with_password_account_raises():
    """OAuth must never silently merge into an existing password account."""
    existing = _make_user(has_password=True)
    svc = _make_service()
    svc._oauth_identity_service.get_oauth_identity = AsyncMock(return_value=None)
    svc._user_service.get_user_by_email = AsyncMock(return_value=existing)

    with pytest.raises(UserAlreadyExistsException):
        await svc.find_or_create_oauth_user(
            provider=SocialAuthProvider.GOOGLE,
            subject="google-new-sub",
            email="ada@example.com",
            first_name="Ada",
            last_name="W",
            avatar_url=None,
            raw_profile={},
            intent=None,
        )

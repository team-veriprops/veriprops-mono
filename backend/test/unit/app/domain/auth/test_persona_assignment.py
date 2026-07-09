"""Unit tests for persona assignment on signup (R2.15).

Verifies:
- intent=verify assigns CUSTOMER persona (PRD §2.1 — "Verify a Property" flow).
- No intent (default) assigns CUSTOMER persona.
- intent=agent assigns AGENT persona.
- OAuth signup without intent assigns CUSTOMER persona.
- OAuth signup with intent=agent assigns AGENT persona.
"""
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.appodus_utils.db.session import db_session_ctx
from main.app.domain.user.auth.session.models import UserPersona
from main.app.domain.user.models import CreateUserDto
from main.appodus_utils import Utils


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


def _make_user(personas=None):
    user = MagicMock()
    user.id = "uid-1"
    user.first_name = "Ada"
    user.email = "ada@example.com"
    user.password_hash = "hashed"
    user.personas = personas or [UserPersona.CUSTOMER]
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


def _base_signup_req(intent: str | None = None):
    from main.app.domain.user.auth.models import SignupRequestDto
    from main.app.domain.user.auth.consent.models import ConsentDocumentType
    payload = {
        "first_name": "Ada",
        "last_name": "Williams",
        "email": "ada@example.com",
        "password": "Sup3rSecure!Pwd",
        "country_code": "NG",
        "dial_code": "+234",
        "phone": "8012345678",
        "country_of_residence": "NG",
        "timezone": "Africa/Lagos",
        "preferred_currency": "NGN",
        "consents": [
            {
                "document_type": ConsentDocumentType.PLATFORM_TERMS.value,
                "consent_version": "1.0.0",
                "accepted_at": Utils.datetime_now().isoformat(),
            },
            {
                "document_type": ConsentDocumentType.PRIVACY_POLICY.value,
                "consent_version": "1.0.0",
                "accepted_at": Utils.datetime_now().isoformat(),
            },
        ],
    }
    if intent is not None:
        payload["intent"] = intent
    return SignupRequestDto.model_validate(payload)


# ── Email/password signup ─────────────────────────────────────────────────────

async def test_signup_intent_verify_assigns_customer():
    """PRD R2.15: 'Verify a Property' signup flow assigns CUSTOMER persona."""
    user = _make_user(personas=[UserPersona.CUSTOMER])
    svc = _make_service()
    svc._user_service.get_user_by_email = AsyncMock(return_value=None)
    svc._otp_service.is_recently_verified = AsyncMock(return_value=True)
    svc._otp_service.consume_verified_marker = AsyncMock()
    svc._consent_service.record_user_consent = AsyncMock()
    svc._session_service.record_event = AsyncMock()

    captured: list[CreateUserDto] = []

    async def capture(dto):
        captured.append(dto)
        return user

    svc._user_service.create_user = capture

    await svc.signup(_base_signup_req(intent="verify"))

    assert len(captured) == 1
    assert UserPersona.CUSTOMER in captured[0].personas


async def test_signup_default_intent_assigns_customer():
    user = _make_user(personas=[UserPersona.CUSTOMER])
    svc = _make_service()
    svc._user_service.get_user_by_email = AsyncMock(return_value=None)
    svc._otp_service.is_recently_verified = AsyncMock(return_value=True)
    svc._otp_service.consume_verified_marker = AsyncMock()
    svc._consent_service.record_user_consent = AsyncMock()
    svc._session_service.record_event = AsyncMock()

    captured: list[CreateUserDto] = []

    async def capture(dto):
        captured.append(dto)
        return user

    svc._user_service.create_user = capture

    await svc.signup(_base_signup_req(intent=None))

    assert UserPersona.CUSTOMER in captured[0].personas


async def test_signup_intent_agent_assigns_agent():
    user = _make_user(personas=[UserPersona.AGENT])
    svc = _make_service()
    svc._user_service.get_user_by_email = AsyncMock(return_value=None)
    svc._otp_service.is_recently_verified = AsyncMock(return_value=True)
    svc._otp_service.consume_verified_marker = AsyncMock()
    svc._consent_service.record_user_consent = AsyncMock()
    svc._session_service.record_event = AsyncMock()

    captured: list[CreateUserDto] = []

    async def capture(dto):
        captured.append(dto)
        return user

    svc._user_service.create_user = capture

    await svc.signup(_base_signup_req(intent="agent"))

    assert UserPersona.AGENT in captured[0].personas
    assert UserPersona.CUSTOMER not in captured[0].personas


# ── OAuth signup ──────────────────────────────────────────────────────────────

async def test_oauth_signup_no_intent_assigns_customer():
    user = _make_user(personas=[UserPersona.CUSTOMER])
    svc = _make_service()
    svc._oauth_identity_service.get_oauth_identity = AsyncMock(return_value=None)
    svc._user_service.get_user_by_email = AsyncMock(return_value=None)
    svc._user_service.update_user = AsyncMock()
    svc._oauth_identity_service.link_oauth = AsyncMock()

    captured: list[CreateUserDto] = []

    async def capture(dto):
        captured.append(dto)
        return user

    svc._user_service.create_user = capture

    from main.app.domain.user.auth.oauth.providers.models import SocialAuthProvider
    await svc.find_or_create_oauth_user(
        provider=SocialAuthProvider.GOOGLE,
        subject="google-sub",
        email="new@example.com",
        first_name="Ada",
        last_name="W",
        avatar_url=None,
        raw_profile={},
        intent=None,
    )

    assert UserPersona.CUSTOMER in captured[0].personas


async def test_oauth_signup_intent_agent_assigns_agent():
    user = _make_user(personas=[UserPersona.AGENT])
    svc = _make_service()
    svc._oauth_identity_service.get_oauth_identity = AsyncMock(return_value=None)
    svc._user_service.get_user_by_email = AsyncMock(return_value=None)
    svc._user_service.update_user = AsyncMock()
    svc._oauth_identity_service.link_oauth = AsyncMock()

    captured: list[CreateUserDto] = []

    async def capture(dto):
        captured.append(dto)
        return user

    svc._user_service.create_user = capture

    from main.app.domain.user.auth.oauth.providers.models import SocialAuthProvider
    await svc.find_or_create_oauth_user(
        provider=SocialAuthProvider.GOOGLE,
        subject="google-sub",
        email="new@example.com",
        first_name="Ada",
        last_name="W",
        avatar_url=None,
        raw_profile={},
        intent="agent",
    )

    assert UserPersona.AGENT in captured[0].personas

"""Unit tests for AuthService.complete_profile (OAuth profile-completion path).

Verifies:
- complete_profile updates the user record with phone_verified=True and returns the user.
- complete_profile raises ValidationException when the phone number belongs to a different user.
"""
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.config.settings import settings
from main.appodus_utils.db.session import db_session_ctx
from main.app.domain.user.auth.models import ProfileCompletionDto
from main.appodus_utils.exception.exceptions import ValidationException


# ── fixtures ──────────────────────────────────────────────────────────────────

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


def _make_service(**overrides):
    from main.app.domain.user.auth.service import AuthService
    svc = object.__new__(AuthService)
    svc._user_service = overrides.get("user_service", AsyncMock())
    svc._consent_service = overrides.get("consent_service", AsyncMock())
    svc._session_service = overrides.get("session_service", AsyncMock())
    svc._otp_service = overrides.get("otp_service", AsyncMock())
    svc._oauth_identity_service = overrides.get("oauth_identity_service", AsyncMock())
    return svc


def _make_user(user_id: str = "uid-1"):
    user = MagicMock()
    user.id = user_id
    user.first_name = "Ada"
    user.last_name = "Obi"
    user.email = "ada@example.com"
    user.phone_verified = True
    return user


def _make_dto(**overrides) -> ProfileCompletionDto:
    return ProfileCompletionDto(
        country_code=overrides.get("country_code", "NG"),
        dial_code=overrides.get("dial_code", "+234"),
        phone=overrides.get("phone", "8012345678"),
        country_of_residence=overrides.get("country_of_residence", "NG"),
        timezone=overrides.get("timezone", "Africa/Lagos"),
        preferred_currency=overrides.get("preferred_currency", "NGN"),
    )


# ── complete_profile — happy path ─────────────────────────────────────────────

async def test_complete_profile_updates_user_and_returns_it(monkeypatch):
    monkeypatch.setattr(settings, "PHONE_VERIFICATION_ENABLED", True)
    updated_user = _make_user()
    svc = _make_service()
    svc._user_service.get_user_by_phone_e164 = AsyncMock(return_value=None)
    svc._user_service.update_user = AsyncMock()
    svc._user_service.get_user_model = AsyncMock(return_value=updated_user)

    result = await svc.complete_profile("uid-1", _make_dto())

    svc._user_service.update_user.assert_called_once()
    update_args = svc._user_service.update_user.call_args[0]
    assert update_args[0] == "uid-1"
    update_dto = update_args[1]
    assert update_dto.phone_verified is True
    assert result is updated_user


async def test_complete_profile_sets_correct_fields():
    updated_user = _make_user()
    svc = _make_service()
    svc._user_service.get_user_by_phone_e164 = AsyncMock(return_value=None)
    svc._user_service.update_user = AsyncMock()
    svc._user_service.get_user_model = AsyncMock(return_value=updated_user)

    dto = _make_dto(
        dial_code="+44",
        phone="7911123456",
        country_code="GB",
        country_of_residence="GB",
        timezone="Europe/London",
        preferred_currency="GBP",
    )
    await svc.complete_profile("uid-1", dto)

    _, update_dto = svc._user_service.update_user.call_args[0]
    assert update_dto.phone_dial_code == "+44"
    assert update_dto.phone == "7911123456"
    assert update_dto.country_of_residence == "GB"
    assert update_dto.timezone == "Europe/London"
    assert update_dto.preferred_currency == "GBP"


# ── complete_profile — phone collision guard ──────────────────────────────────

async def test_complete_profile_raises_when_phone_belongs_to_another_user():
    other_user = _make_user(user_id="uid-other")
    svc = _make_service()
    svc._user_service.get_user_by_phone_e164 = AsyncMock(return_value=other_user)

    with pytest.raises(ValidationException, match="phone number already exists"):
        await svc.complete_profile("uid-1", _make_dto())

    svc._user_service.update_user.assert_not_called()


async def test_complete_profile_allows_same_user_to_re_complete():
    """A user can call profile_complete again with their own phone — not a collision."""
    same_user = _make_user(user_id="uid-1")
    svc = _make_service()
    svc._user_service.get_user_by_phone_e164 = AsyncMock(return_value=same_user)
    svc._user_service.update_user = AsyncMock()
    svc._user_service.get_user_model = AsyncMock(return_value=same_user)

    result = await svc.complete_profile("uid-1", _make_dto())

    svc._user_service.update_user.assert_called_once()
    assert result is same_user

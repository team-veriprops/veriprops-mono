"""Signup honours the phone-verification toggle."""
from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.config.settings import settings
from main.app.domain.user.auth.consent.models import ConsentDocumentType
from main.app.domain.user.auth.models import OtpChannel, SignupRequestDto, UserConsentInputDto
from main.app.domain.user.auth.service import AuthService
from main.appodus_utils import Utils
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.exception.exceptions import ValidationException


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


def _payload() -> SignupRequestDto:
    return SignupRequestDto.model_validate({
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
            UserConsentInputDto(
                document_type=ConsentDocumentType.PLATFORM_TERMS,
                consent_version="1.0.0",
                accepted_at=Utils.datetime_now(),
            ),
            UserConsentInputDto(
                document_type=ConsentDocumentType.PRIVACY_POLICY,
                consent_version="1.0.0",
                accepted_at=Utils.datetime_now(),
            ),
        ],
    })


def _service(email_verified=True, phone_verified=False):
    user_service = MagicMock()
    user_service.get_user_by_email = AsyncMock(return_value=None)
    created = MagicMock()
    created.id = "user-1"
    user_service.create_user = AsyncMock(return_value=created)

    otp_service = MagicMock()

    async def _is_verified(channel, _recipient):
        return email_verified if channel == OtpChannel.EMAIL else phone_verified

    otp_service.is_recently_verified = AsyncMock(side_effect=_is_verified)
    otp_service.consume_verified_marker = AsyncMock()

    consent_service = MagicMock()
    consent_service.record_user_consent = AsyncMock()
    session_service = MagicMock()
    session_service.record_event = AsyncMock()

    svc = AuthService(
        user_service=user_service,
        consent_service=consent_service,
        session_service=session_service,
        otp_service=otp_service,
        oauth_identity_service=MagicMock(),
    )
    return svc, user_service, otp_service


class TestSignupPhoneFlag:
    async def test_phone_required_when_enabled_and_unverified(self, monkeypatch):
        monkeypatch.setattr(settings, "PHONE_VERIFICATION_ENABLED", True)
        svc, _, _ = _service(phone_verified=False)
        with pytest.raises(ValidationException):
            await svc.signup(_payload())

    async def test_signup_succeeds_without_phone_when_disabled(self, monkeypatch):
        monkeypatch.setattr(settings, "PHONE_VERIFICATION_ENABLED", False)
        svc, user_service, otp_service = _service(phone_verified=False)

        await svc.signup(_payload())

        create_dto = user_service.create_user.await_args.args[0]
        assert create_dto.phone_verified is False
        # The phone marker is never consumed when phone verification is off.
        consumed_channels = [c.args[0] for c in otp_service.consume_verified_marker.await_args_list]
        assert OtpChannel.PHONE not in consumed_channels
        assert OtpChannel.EMAIL in consumed_channels

    async def test_signup_requires_phone_marker_when_enabled(self, monkeypatch):
        monkeypatch.setattr(settings, "PHONE_VERIFICATION_ENABLED", True)
        svc, user_service, _ = _service(phone_verified=True)

        await svc.signup(_payload())

        create_dto = user_service.create_user.await_args.args[0]
        assert create_dto.phone_verified is True

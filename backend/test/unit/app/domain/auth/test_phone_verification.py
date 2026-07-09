"""Phase-5 phone verification (PRD §5). When PHONE_VERIFICATION_ENABLED=false the number is
collected but unverified at signup; these authenticated helpers verify the logged-in user's
own phone and flip phone_verified so the payment gate can be satisfied. Repos/services mocked."""
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from unittest.mock import AsyncMock, MagicMock

from main.app.domain.user.auth.service import AuthService
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.exception.exceptions import InvalidTokenException


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


def _service():
    svc = object.__new__(AuthService)
    svc._user_service = MagicMock()
    svc._otp_service = MagicMock()
    svc._user_service.get_user_model = AsyncMock(
        return_value=SimpleNamespace(
            phone_dial_code="+234", phone="8030000001", first_name="Ada", last_name="QA",
        )
    )
    svc._user_service.mark_phone_verified = AsyncMock()
    svc._otp_service.verify_otp = AsyncMock()
    svc._otp_service.consume_verified_marker = AsyncMock()
    return svc


class TestVerifyPhoneForUser:
    async def test_valid_code_verifies_then_marks_and_consumes(self):
        svc = _service()
        await svc.verify_phone_for_user("u-1", "654123")

        # OTP is checked against the user's own phone, keyed to the user id.
        svc._otp_service.verify_otp.assert_awaited_once()
        _, kwargs = svc._otp_service.verify_otp.call_args
        assert kwargs["user_id"] == "u-1"
        svc._user_service.mark_phone_verified.assert_awaited_once_with("u-1")
        svc._otp_service.consume_verified_marker.assert_awaited_once()

    async def test_invalid_code_does_not_mark_verified(self):
        svc = _service()
        svc._otp_service.verify_otp = AsyncMock(side_effect=InvalidTokenException("bad code"))

        with pytest.raises(InvalidTokenException):
            await svc.verify_phone_for_user("u-1", "000000")

        # A failed OTP must never flip phone_verified.
        svc._user_service.mark_phone_verified.assert_not_called()
        svc._otp_service.consume_verified_marker.assert_not_called()


class TestSendPhoneOtpForUser:
    async def test_sends_otp_to_users_own_phone(self):
        svc = _service()
        svc.send_otp = AsyncMock(return_value=30)

        resend_in = await svc.send_phone_otp_for_user("u-1")

        assert resend_in == 30
        _, kwargs = svc.send_otp.call_args
        assert kwargs["dial_code"] == "+234" and kwargs["phone"] == "8030000001"
        assert kwargs["user_id"] == "u-1"

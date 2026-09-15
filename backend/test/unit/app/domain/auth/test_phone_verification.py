"""Pay-step phone verification (PRD §10.5). When PHONE_VERIFICATION_ENABLED=false the number is
collected but unverified at signup; these authenticated helpers let the logged-in customer confirm
or correct that number, OTP-verify it, and only then write it to their profile so the payment gate
can be satisfied. Repos/services mocked."""
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from unittest.mock import AsyncMock, MagicMock

from main.app.domain.user.auth.models import PhoneOtpSendDto, VerifyPhoneDto
from main.app.domain.user.auth.service import AuthService
from main.app.domain.user.models import OAUTH_PLACEHOLDER_PHONE
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.exception.exceptions import InvalidTokenException, ValidationException


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


def _service(*, phone="8030000001", phone_verified=False, owner_of_number=None):
    svc = object.__new__(AuthService)
    svc._user_service = MagicMock()
    svc._otp_service = MagicMock()
    svc._user_service.get_user_model = AsyncMock(
        return_value=SimpleNamespace(
            id="u-1", phone_country_code="NG", phone_dial_code="+234", phone=phone,
            phone_verified=phone_verified, first_name="Ada", last_name="QA",
        )
    )
    svc._user_service.get_user_by_phone_e164 = AsyncMock(return_value=owner_of_number)
    svc._user_service.update_user = AsyncMock()
    svc._otp_service.verify_otp = AsyncMock()
    svc._otp_service.consume_verified_marker = AsyncMock()
    svc.send_otp = AsyncMock(return_value=30)
    return svc


_NEW_NUMBER = dict(country_code="NG", dial_code="+234", phone="8129998888")


class TestSendPhoneOtpForUser:
    async def test_without_a_number_sends_to_the_profile_phone(self):
        svc = _service()

        resend_in = await svc.send_phone_otp_for_user("u-1", PhoneOtpSendDto())

        assert resend_in == 30
        _, kwargs = svc.send_otp.call_args
        assert kwargs["dial_code"] == "+234" and kwargs["phone"] == "8030000001"
        assert kwargs["user_id"] == "u-1"

    async def test_an_entered_number_is_targeted_without_touching_the_profile(self):
        svc = _service()

        await svc.send_phone_otp_for_user("u-1", PhoneOtpSendDto(**_NEW_NUMBER))

        _, kwargs = svc.send_otp.call_args
        assert kwargs["phone"] == "8129998888"
        # The profile only changes once the customer proves the number is theirs.
        svc._user_service.update_user.assert_not_called()

    @pytest.mark.parametrize("profile_phone", [OAUTH_PLACEHOLDER_PHONE, "", None])
    async def test_no_usable_number_asks_the_customer_to_enter_one(self, profile_phone):
        svc = _service(phone=profile_phone)

        with pytest.raises(ValidationException):
            await svc.send_phone_otp_for_user("u-1", PhoneOtpSendDto())
        svc.send_otp.assert_not_called()

    async def test_a_number_held_by_another_account_is_rejected(self):
        svc = _service(owner_of_number=SimpleNamespace(id="someone-else"))

        with pytest.raises(ValidationException):
            await svc.send_phone_otp_for_user("u-1", PhoneOtpSendDto(**_NEW_NUMBER))
        svc.send_otp.assert_not_called()

    async def test_the_customers_own_number_is_not_a_conflict(self):
        svc = _service(owner_of_number=SimpleNamespace(id="u-1"))

        await svc.send_phone_otp_for_user("u-1", PhoneOtpSendDto())

        svc.send_otp.assert_awaited_once()

    async def test_a_verified_number_cannot_be_swapped_here(self):
        svc = _service(phone_verified=True)

        with pytest.raises(ValidationException):
            await svc.send_phone_otp_for_user("u-1", PhoneOtpSendDto(**_NEW_NUMBER))
        svc.send_otp.assert_not_called()


class TestVerifyPhoneForUser:
    async def test_valid_code_writes_the_proven_number_and_consumes_the_marker(self):
        svc = _service()

        await svc.verify_phone_for_user("u-1", VerifyPhoneDto(code="654123", **_NEW_NUMBER))

        # OTP is checked against the entered number, keyed to the user id.
        args, kwargs = svc._otp_service.verify_otp.call_args
        assert args[1].number == "8129998888"
        assert kwargs["user_id"] == "u-1"
        user_id, dto = svc._user_service.update_user.call_args.args
        assert user_id == "u-1"
        assert dto.phone == "8129998888" and dto.phone_dial_code == "+234"
        assert dto.phone_country_code == "NG" and dto.phone_e164 == "+2348129998888"
        assert dto.phone_verified is True
        svc._otp_service.consume_verified_marker.assert_awaited_once()

    async def test_valid_code_without_a_number_verifies_the_profile_phone(self):
        svc = _service()

        await svc.verify_phone_for_user("u-1", VerifyPhoneDto(code="654123"))

        _, dto = svc._user_service.update_user.call_args.args
        assert dto.phone == "8030000001" and dto.phone_verified is True

    async def test_invalid_code_writes_nothing(self):
        svc = _service()
        svc._otp_service.verify_otp = AsyncMock(side_effect=InvalidTokenException("bad code"))

        with pytest.raises(InvalidTokenException):
            await svc.verify_phone_for_user("u-1", VerifyPhoneDto(code="000000", **_NEW_NUMBER))

        # A failed OTP must never change the profile or flip phone_verified.
        svc._user_service.update_user.assert_not_called()
        svc._otp_service.consume_verified_marker.assert_not_called()

    async def test_a_number_claimed_by_another_account_meanwhile_is_rejected(self):
        svc = _service(owner_of_number=SimpleNamespace(id="someone-else"))

        with pytest.raises(ValidationException):
            await svc.verify_phone_for_user("u-1", VerifyPhoneDto(code="654123", **_NEW_NUMBER))
        svc._user_service.update_user.assert_not_called()

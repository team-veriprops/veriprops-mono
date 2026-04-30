"""Pure-logic tests for OTP helpers — no DI, no DB."""
import pytest

from main.app.domain.user.auth.models import OtpChannel
from main.app.domain.user.auth.otp_service import (
    _failure_key,
    _otp_key,
    _phone_e164,
    _resend_key,
    recipient_for,
)
from main.appodus_utils.exception.exceptions import InvalidTokenException


class TestPhoneE164:
    def test_basic_format(self):
        assert _phone_e164("+234", "8012345678") == "+2348012345678"

    def test_strips_non_digits(self):
        assert _phone_e164("+234", "(801) 234-5678") == "+2348012345678"

    def test_no_leading_plus_when_dial_has_none(self):
        assert _phone_e164("234", "8012345678") == "+2348012345678"


class TestOtpKeys:
    def test_otp_key_lowercases(self):
        assert _otp_key(OtpChannel.EMAIL, "Foo@Example.com") == "otp:EMAIL:foo@example.com"

    def test_resend_key_distinct_from_otp_key(self):
        recipient = "+2348012345678"
        assert _otp_key(OtpChannel.PHONE, recipient) != _resend_key(OtpChannel.PHONE, recipient)

    def test_failure_key_distinct(self):
        recipient = "test@example.com"
        keys = {
            _otp_key(OtpChannel.EMAIL, recipient),
            _resend_key(OtpChannel.EMAIL, recipient),
            _failure_key(OtpChannel.EMAIL, recipient),
        }
        assert len(keys) == 3


class TestRecipientFor:
    def test_email_channel_returns_lowercased_email(self):
        assert recipient_for(OtpChannel.EMAIL, email="Foo@Example.com",
                             dial_code=None, phone=None) == "foo@example.com"

    def test_phone_channel_builds_e164(self):
        assert recipient_for(OtpChannel.PHONE, email=None,
                             dial_code="+234", phone="8012345678") == "+2348012345678"

    def test_email_channel_without_email_raises(self):
        with pytest.raises(InvalidTokenException):
            recipient_for(OtpChannel.EMAIL, email=None, dial_code=None, phone=None)

    def test_phone_channel_without_phone_raises(self):
        with pytest.raises(InvalidTokenException):
            recipient_for(OtpChannel.PHONE, email=None, dial_code="+234", phone=None)

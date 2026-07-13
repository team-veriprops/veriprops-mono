"""Time-bound message expiry plumbing (§2 OTP / password reset).

OTP codes are last-write-wins in KV with OTP_CODE_TTL_SECONDS, so a delivery
retry past that window carries a dead code. `send_verification_msg` must stamp
`expires_at ≈ now + OTP_TTL` on the outbound message so the retry sweep never
re-dispatches it beyond usefulness.
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

from kink import di

from main.app.config.settings import settings
from main.app.domain.user.auth.otp_service import OTP_TTL, send_verification_msg
from main.app.domain.user.user_messages import AccountSecurityMessages
from main.appodus_utils.integrations.messaging.models import EmailRecipient, PhoneNumber


async def _capture_send(recipient):
    """Swap the DI-registered sender for a mock, run send_verification_msg, return it."""
    sender = AsyncMock(spec=AccountSecurityMessages)
    original = di[AccountSecurityMessages]
    di[AccountSecurityMessages] = sender
    try:
        await send_verification_msg(recipient=recipient, code="654123")
    finally:
        di[AccountSecurityMessages] = original
    return sender


class TestOtpExpiresAt:
    async def test_email_otp_carries_otp_ttl_horizon(self):
        before = datetime.now(timezone.utc)
        sender = await _capture_send(
            EmailRecipient(email="user@example.com", fullname="Ada QA"))

        call = sender.send_direct_email_verification_message.call_args
        expires_at = call.kwargs["expires_at"]
        assert before + OTP_TTL - timedelta(seconds=5) <= expires_at <= \
            datetime.now(timezone.utc) + OTP_TTL

    async def test_phone_otp_carries_otp_ttl_horizon(self):
        before = datetime.now(timezone.utc)
        sender = await _capture_send(PhoneNumber(dial_code="+234", number="8012345678"))

        call = sender.send_direct_phone_verification_message.call_args
        expires_at = call.kwargs["expires_at"]
        assert before + OTP_TTL - timedelta(seconds=5) <= expires_at <= \
            datetime.now(timezone.utc) + OTP_TTL

    def test_otp_ttl_reads_setting(self):
        assert OTP_TTL == timedelta(seconds=settings.OTP_CODE_TTL_SECONDS)

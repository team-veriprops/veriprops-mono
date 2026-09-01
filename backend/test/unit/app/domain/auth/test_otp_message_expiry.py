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
from main.app.domain.user.auth.models import OtpChannel
from main.app.domain.user.auth.otp_service import OTP_TTL, _otp_key, send_verification_msg
from main.app.domain.user.user_messages import AccountSecurityMessages
from main.appodus_utils.integrations.messaging.models import EmailRecipient, PhoneNumber


async def _capture_send(recipient, channel: OtpChannel = OtpChannel.EMAIL):
    """Swap the DI-registered sender for a mock, run send_verification_msg, return it."""
    sender = AsyncMock(spec=AccountSecurityMessages)
    original = di[AccountSecurityMessages]
    di[AccountSecurityMessages] = sender
    try:
        await send_verification_msg(recipient=recipient, code="654123", channel=channel)
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
        sender = await _capture_send(
            PhoneNumber(dial_code="+234", number="8012345678"), OtpChannel.PHONE)

        call = sender.send_direct_phone_verification_message.call_args
        expires_at = call.kwargs["expires_at"]
        assert before + OTP_TTL - timedelta(seconds=5) <= expires_at <= \
            datetime.now(timezone.utc) + OTP_TTL

    async def test_whatsapp_link_otp_carries_otp_ttl_horizon(self):
        before = datetime.now(timezone.utc)
        sender = await _capture_send(
            PhoneNumber(dial_code="+234", number="8012345678"), OtpChannel.WHATSAPP)

        call = sender.send_whatsapp_link_verification_message.call_args
        expires_at = call.kwargs["expires_at"]
        assert before + OTP_TTL - timedelta(seconds=5) <= expires_at <= \
            datetime.now(timezone.utc) + OTP_TTL

    def test_otp_ttl_reads_setting(self):
        assert OTP_TTL == timedelta(seconds=settings.OTP_CODE_TTL_SECONDS)


class TestOtpChannelRouting:
    """§7.4.4 / D46: the linking code goes over WhatsApp, and only over WhatsApp.

    Delivering it anywhere else would prove control of something other than the WhatsApp
    number being linked, which is the one fact the whole flow exists to establish.
    """

    async def test_a_whatsapp_channel_otp_never_goes_out_as_sms(self):
        sender = await _capture_send(
            PhoneNumber(dial_code="+234", number="8012345678"), OtpChannel.WHATSAPP)
        sender.send_direct_phone_verification_message.assert_not_called()
        sender.send_whatsapp_link_verification_message.assert_called_once()

    async def test_a_phone_channel_otp_still_goes_out_as_sms(self):
        sender = await _capture_send(
            PhoneNumber(dial_code="+234", number="8012345678"), OtpChannel.PHONE)
        sender.send_whatsapp_link_verification_message.assert_not_called()
        sender.send_direct_phone_verification_message.assert_called_once()

    def test_otp_keys_are_namespaced_by_channel(self):
        # The same number linked over WhatsApp and verified over SMS must hold two
        # independent codes: sharing a key would let a code issued for one purpose be
        # spent for the other.
        recipient = PhoneNumber(dial_code="+234", number="8012345678")
        assert _otp_key(OtpChannel.WHATSAPP, recipient) != _otp_key(OtpChannel.PHONE, recipient)

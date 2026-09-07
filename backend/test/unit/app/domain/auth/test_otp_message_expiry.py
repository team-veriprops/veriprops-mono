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
from main.appodus_utils.integrations.messaging.models import (
    EmailRecipient,
    MessageContext,
    PhoneNumber,
)


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
    """§26.4.4: the linking code goes over WhatsApp first.

    WhatsApp is the primary transport because the number being linked *is* a WhatsApp
    number, so a code arriving there is the most direct proof of control. SMS is the
    PRD's named fallback and only runs when the WhatsApp send fails (D60, below).
    """

    async def test_a_successful_whatsapp_otp_is_not_also_sent_as_sms(self):
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


class TestWhatsAppSmsFallback:
    """§26.4.4 / D60 — WhatsApp first, SMS to the same number if that fails.

    A WhatsApp send can fail for reasons that have nothing to do with the customer: an
    unapproved template, a Meta outage, a number with no WhatsApp account. Without the
    fallback each of those dead-ends the linking flow for somebody who did nothing wrong.
    """

    @staticmethod
    async def _send_with_whatsapp_failing(error: Exception):
        sender = AsyncMock(spec=AccountSecurityMessages)
        sender.send_whatsapp_link_verification_message.side_effect = error
        original = di[AccountSecurityMessages]
        di[AccountSecurityMessages] = sender
        try:
            await send_verification_msg(
                recipient=PhoneNumber(dial_code="+234", number="8012345678"),
                code="654123",
                channel=OtpChannel.WHATSAPP,
            )
        finally:
            di[AccountSecurityMessages] = original
        return sender

    async def test_falls_back_to_sms_when_the_whatsapp_send_fails(self):
        sender = await self._send_with_whatsapp_failing(RuntimeError("Meta is down"))
        sender.send_direct_phone_verification_message.assert_called_once()

    async def test_the_fallback_carries_the_same_code_to_the_same_number(self):
        # A different code would be unverifiable: the OTP is stored once, under the
        # WhatsApp channel key, whichever transport ends up carrying it.
        sender = await self._send_with_whatsapp_failing(RuntimeError("Meta is down"))
        call = sender.send_direct_phone_verification_message.call_args
        assert call.kwargs["context"][MessageContext.OTP] == "654123"
        assert call.kwargs["recipient"].phone.international_number == "+2348012345678"

    async def test_no_sms_when_whatsapp_succeeds(self):
        # The fallback is a fallback, not a second send — two codes to one customer for
        # one request reads as a compromised account.
        sender = await _capture_send(
            PhoneNumber(dial_code="+234", number="8012345678"), OtpChannel.WHATSAPP)
        sender.send_whatsapp_link_verification_message.assert_called_once()
        sender.send_direct_phone_verification_message.assert_not_called()

    async def test_a_failing_fallback_never_propagates(self):
        # Delivery is best-effort: the code is already stored, and raising here would
        # turn an undelivered message into a failed API call for the customer.
        sender = AsyncMock(spec=AccountSecurityMessages)
        sender.send_whatsapp_link_verification_message.side_effect = RuntimeError("meta")
        sender.send_direct_phone_verification_message.side_effect = RuntimeError("sms")
        original = di[AccountSecurityMessages]
        di[AccountSecurityMessages] = sender
        try:
            await send_verification_msg(
                recipient=PhoneNumber(dial_code="+234", number="8012345678"),
                code="654123",
                channel=OtpChannel.WHATSAPP,
            )
        finally:
            di[AccountSecurityMessages] = original

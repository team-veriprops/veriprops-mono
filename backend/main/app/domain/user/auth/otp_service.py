"""OTP issuance & verification — uses KeyValueService (Redis-backed when configured)."""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger

from datetime import datetime, timedelta
from typing import Optional, Union

from main.appodus_utils.db.types.phone import PhoneNumber
from main.appodus_utils.integrations.messaging.models import EmailRecipient, MessageRequestRecipient, MessageContext

from kink import di, inject

from main.app.config.settings import settings
from main.app.domain.user.auth.models import OtpChannel
from main.app.domain.user.auth.session.models import SecurityEventType
from main.app.domain.user.auth.session.service import SessionService
from main.appodus_utils import Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.domain.key_value.service import KeyValueService
from main.appodus_utils.exception.exceptions import (
    InvalidTokenException,
    RateLimitException,
)

logger: Logger = di["logger"]

# Sent-code validity window. `_validity_label()` derives the human-readable string
# shown in the delivery message from this same value so the two never drift.
OTP_TTL = timedelta(seconds=settings.OTP_CODE_TTL_SECONDS)
MAX_RESENDS = settings.OTP_MAX_RESENDS
RESEND_LOCKOUT = timedelta(seconds=settings.OTP_RESEND_LOCKOUT_SECONDS)
MAX_FAILURES = settings.OTP_MAX_FAILURES
# After a successful OTP verification we mint a short-lived "verified" marker so the
# signup endpoint can confirm the user actually completed the OTP step, letting the
# user finish a multi-step wizard without re-verifying.
OTP_VERIFIED_TTL = timedelta(seconds=settings.OTP_VERIFIED_MARKER_TTL_SECONDS)


def _validity_label() -> str:
    """Human-readable OTP validity (e.g. "10 minutes") derived from OTP_TTL."""
    minutes = int(OTP_TTL.total_seconds() // 60)
    return f"{minutes} minutes"


def _phone_e164(dial_code: str, phone: str) -> str:
    digits = "".join(c for c in (dial_code + phone) if c.isdigit())
    return f"+{digits}"


def _to_recipient_str(recipient: Union[str, EmailRecipient, PhoneNumber]) -> str:
    if isinstance(recipient, str):
        return recipient.lower()
    if isinstance(recipient, EmailRecipient):
        return recipient.email.lower()
    return recipient.international_number.lower()


def _otp_key(channel: OtpChannel, recipient: Union[str, EmailRecipient, PhoneNumber]) -> str:
    return f"otp:{channel.value}:{_to_recipient_str(recipient)}"


def _resend_key(channel: OtpChannel, recipient: Union[str, EmailRecipient, PhoneNumber]) -> str:
    return f"otp_resend:{channel.value}:{_to_recipient_str(recipient)}"


def _failure_key(channel: OtpChannel, recipient: Union[str, EmailRecipient, PhoneNumber]) -> str:
    return f"otp_fail:{channel.value}:{_to_recipient_str(recipient)}"


def _verified_key(channel: OtpChannel, recipient_str: str) -> str:
    return f"otp_verified:{channel.value}:{recipient_str.lower()}"


@inject
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class OtpService:
    def __init__(
            self,
            kv: KeyValueService,
            session_service: SessionService,
    ):
        self._kv = kv
        self._session_service = session_service

    async def send_otp(
            self,
            channel: OtpChannel,
            recipient: Union[EmailRecipient, PhoneNumber],
            *,
            user_id: Optional[str] = None,
            ip_address: Optional[str] = None,
    ) -> int:
        """Issue (or rotate) an OTP and dispatch via the chosen channel.
        Returns seconds until the user can request a resend (TTL of the OTP)."""
        r_key = _resend_key(channel, recipient)
        recent = await self._kv.get(r_key)
        attempts = int(recent or 0) + 1
        if attempts > MAX_RESENDS:
            raise RateLimitException(service="otp", message="Too many resend attempts; try again later.")

        code = Utils.get_otp_code()
        await self._kv.set(_otp_key(channel, recipient), OTP_TTL, code)
        await self._kv.set(r_key, RESEND_LOCKOUT, attempts)

        await send_verification_msg(recipient=recipient, code=code, channel=channel)
        await self._session_service.record_event(
            SecurityEventType.OTP_SENT,
            f"OTP sent via {channel.value.lower()}",
            user_id=user_id,
            ip_address=ip_address,
        )
        return int(OTP_TTL.total_seconds())

    async def verify_otp(
            self,
            channel: OtpChannel,
            recipient: Union[EmailRecipient, PhoneNumber],
            code: str,
            *,
            user_id: Optional[str] = None,
            ip_address: Optional[str] = None,
    ) -> None:
        f_key = _failure_key(channel, recipient)
        failures = int(await self._kv.get(f_key) or 0)
        if failures >= MAX_FAILURES:
            raise RateLimitException(service="otp", message="Too many invalid attempts; request a new code.")

        stored = await self._kv.get(_otp_key(channel, recipient))
        stored_str = stored.decode("utf-8") if isinstance(stored, bytes) else stored
        if not stored_str or str(stored_str) != str(code):
            await self._kv.set(f_key, OTP_TTL, failures + 1)
            await self._session_service.record_event(
                SecurityEventType.OTP_FAILURE,
                f"OTP verification failed via {channel.value.lower()}",
                user_id=user_id,
                ip_address=ip_address,
            )
            raise InvalidTokenException("Invalid or expired verification code.")

        # Clear keys on success and mint a short-lived verified marker so the
        # signup endpoint can confirm the user actually completed this OTP.
        await self._kv.delete(_otp_key(channel, recipient))
        await self._kv.delete(f_key)
        await self._kv.set(
            _verified_key(channel, _to_recipient_str(recipient)),
            OTP_VERIFIED_TTL,
            "1",
        )

    async def is_recently_verified(self, channel: OtpChannel, recipient_str: str) -> bool:
        marker = await self._kv.get(_verified_key(channel, recipient_str))
        return bool(marker)

    async def consume_verified_marker(self, channel: OtpChannel, recipient_str: str) -> None:
        await self._kv.delete(_verified_key(channel, recipient_str))


def recipient_for(channel: OtpChannel, *, email: Optional[str], dial_code: Optional[str], phone: Optional[str],
                  fullname: Optional[str] = None) -> Union[EmailRecipient, PhoneNumber]:
    if channel == OtpChannel.EMAIL:
        if not email:
            raise InvalidTokenException("Email is required for email OTP.")
        return EmailRecipient(email=email.lower(), fullname=fullname)
    if not dial_code or not phone:
        raise InvalidTokenException("Dial code + phone required for phone OTP.")
    return PhoneNumber(dial_code=dial_code, number=phone)


async def send_verification_msg(
        recipient: Union[EmailRecipient, PhoneNumber],
        code: str,
        channel: OtpChannel = OtpChannel.EMAIL,
) -> None:
    from main.app.domain.user.user_messages import AccountSecurityMessages
    account_security_messages = di[AccountSecurityMessages]

    # The code is useless (or stale — resends overwrite it) past its validity, so
    # cap delivery retries at the OTP window instead of the full retry ladder.
    expires_at = Utils.datetime_now() + OTP_TTL

    try:
        if channel == OtpChannel.WHATSAPP:
            # PRD §7.4.4: WhatsApp account linking delivers its code over WhatsApp itself,
            # using the §7.7 `otp_auth` template, and falls back to SMS on the same number
            # (D60, amending D46). The code is stored under the WHATSAPP channel key
            # either way, so verification is unaffected by which transport carried it.
            await _send_whatsapp_otp_with_sms_fallback(
                account_security_messages, recipient, code, expires_at
            )
        elif isinstance(recipient, EmailRecipient):
            firstname, _, lastname = Utils.parse_fullname(str(recipient.fullname))

            await account_security_messages.send_direct_email_verification_message(
                recipient=MessageRequestRecipient(
                    fullname=recipient.fullname,
                    email=recipient.email
                ),
                context={
                    MessageContext.FULL_NAME: recipient.fullname,
                    MessageContext.FIRST_NAME: firstname,
                    MessageContext.LAST_NAME: lastname,
                    MessageContext.OTP: code,
                    MessageContext.VALIDITY: _validity_label(),
                },
                expires_at=expires_at
            )
        else:
            await account_security_messages.send_direct_phone_verification_message(
                recipient=MessageRequestRecipient(
                    phone=recipient
                ),
                context={
                    MessageContext.OTP: code,
                    MessageContext.VALIDITY: _validity_label(),
                },
                expires_at=expires_at
            )
    except Exception as e:
        logger.warning("OTP delivery failed for {} via {}: {}", recipient, channel.value, e)


async def _send_whatsapp_otp_with_sms_fallback(
        account_security_messages,
        recipient: PhoneNumber,
        code: str,
        expires_at: datetime,
) -> None:
    """Deliver an account-linking OTP over WhatsApp, falling back to SMS (§7.4.4, D60).

    WhatsApp is the primary transport because the number being linked *is* a WhatsApp
    number, so a code that arrives there is the most direct proof of control. But a
    WhatsApp send can fail for reasons that have nothing to do with the customer — an
    unapproved template, a Meta outage, a number with no WhatsApp account — and a linking
    flow that dead-ends on any of those strands somebody who did nothing wrong.

    SMS to the same number is the fallback §7.4.4 names. The provider chain is the
    messaging router's existing one (Termii → Twilio for +234, the mock provider in
    dev/test), so this needs no new provider decision — which is the blocker D46 deferred
    on, and which the router had already settled.

    The fallback is deliberately **not** silent: a customer who received the code by SMS
    got the experience the PRD's second choice describes, and that is worth seeing in the
    logs when diagnosing why linking rates differ from send counts.
    """
    context = {MessageContext.OTP: code, MessageContext.VALIDITY: _validity_label()}
    try:
        await account_security_messages.send_whatsapp_link_verification_message(
            recipient=MessageRequestRecipient(phone=recipient),
            context=context,
            expires_at=expires_at,
        )
        return
    except Exception as e:
        logger.warning(
            "WhatsApp OTP delivery failed for {}; falling back to SMS (§7.4.4): {}",
            recipient.international_number, e,
        )

    await account_security_messages.send_direct_phone_verification_message(
        recipient=MessageRequestRecipient(phone=recipient),
        context=context,
        expires_at=expires_at,
    )

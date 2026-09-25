"""OTP issuance & verification.

Codes, attempt counters and verified markers live in the SQL key/value store
(`KeyValueService`), whose writes commit on their own: a wrong guess is counted even though
the request then fails. Counters are reserved atomically before they are checked, and codes and
markers are consumed atomically, so concurrent requests can't exceed a limit or reuse a code.
"""
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
from main.app.domain.user.auth.models import OtpChannel, OtpSendResultDto
from main.app.domain.user.auth.session.failure_recorder import AuthFailureRecorder
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
            failure_recorder: AuthFailureRecorder,
    ):
        self._kv = kv
        self._session_service = session_service
        # A wrong guess is logged here, not in the caller's transaction: the rejection that
        # follows would roll it back.
        self._failures = failure_recorder

    async def send_otp(
            self,
            channel: OtpChannel,
            recipient: Union[EmailRecipient, PhoneNumber],
            *,
            user_id: Optional[str] = None,
            ip_address: Optional[str] = None,
    ) -> OtpSendResultDto:
        """Issue (or rotate) an OTP and dispatch it over *channel*.

        Reports the resend window (the OTP's TTL) and whether dispatch completed. Delivery stays
        best-effort — a failed send must not fail the request, because the code is stored and the
        retry ladder may still carry it — but the caller can now tell the user when a code is not
        on its way instead of presenting an entry box for it."""
        # Reserve this send's slot atomically; at the limit nothing is written, so a refused
        # resend neither counts nor extends the lockout.
        attempt = await self._kv.incr(
            _resend_key(channel, recipient), RESEND_LOCKOUT, sliding=True, limit=MAX_RESENDS,
        )
        if attempt is None:
            raise RateLimitException(service="otp", message="Too many resend attempts; try again later.")

        code = Utils.get_otp_code()
        await self._kv.set(_otp_key(channel, recipient), OTP_TTL, code)

        delivered = await send_verification_msg(recipient=recipient, code=code, channel=channel)
        await self._session_service.record_event(
            SecurityEventType.OTP_SENT,
            f"OTP sent via {channel.value.lower()}",
            user_id=user_id,
            ip_address=ip_address,
        )
        return OtpSendResultDto(
            resend_in=int(OTP_TTL.total_seconds()), delivered=delivered,
        )

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
        # Reserve this attempt's slot before judging it, so parallel guesses can't all pass a
        # stale count. Only a failed attempt keeps its slot: success deletes the counter.
        attempt = await self._kv.incr(f_key, OTP_TTL, sliding=True, limit=MAX_FAILURES)
        if attempt is None:
            raise RateLimitException(service="otp", message="Too many invalid attempts; request a new code.")

        otp_key = _otp_key(channel, recipient)
        stored = await self._kv.get(otp_key)
        # The pop decides between two concurrent correct guesses: only one consumes the code.
        if not stored or str(stored) != str(code) or await self._kv.pop(otp_key) is None:
            await self._failures.record_event(
                SecurityEventType.OTP_FAILURE,
                f"OTP verification failed via {channel.value.lower()}",
                user_id=user_id,
                ip_address=ip_address,
            )
            raise InvalidTokenException("Invalid or expired verification code.")

        # Clear the counter on success and mint a short-lived verified marker so the
        # signup endpoint can confirm the user actually completed this OTP.
        await self._kv.delete(f_key)
        await self._kv.set(
            _verified_key(channel, _to_recipient_str(recipient)),
            OTP_VERIFIED_TTL,
            "1",
        )

    async def is_recently_verified(self, channel: OtpChannel, recipient_str: str) -> bool:
        marker = await self._kv.get(_verified_key(channel, recipient_str))
        return bool(marker)

    async def consume_verified_marker(self, channel: OtpChannel, recipient_str: str) -> bool:
        """Consume the marker; True for exactly one caller, so one OTP backs one signup."""
        return await self._kv.pop(_verified_key(channel, recipient_str)) is not None


def recipient_for(channel: OtpChannel, *, email: Optional[str], dial_code: Optional[str], phone: Optional[str],
                  fullname: Optional[str] = None) -> Union[EmailRecipient, PhoneNumber]:
    if channel == OtpChannel.EMAIL:
        if not email:
            raise InvalidTokenException("Email is required for email OTP.")
        return EmailRecipient(email=email.lower(), fullname=fullname)
    if not dial_code or not phone:
        raise InvalidTokenException("Dial code + phone required for phone OTP.")
    return PhoneNumber(dial_code=dial_code, number=phone)


def _dispatch_completed(result) -> bool:
    """A dispatch counts as delivered once at least one channel reported success.

    `send_bulk` buckets failures rather than raising, so an all-channels-failed dispatch returns
    normally — the successes list is the only thing that distinguishes it from a real send.
    """
    return bool(result is not None and result.successes)


async def send_verification_msg(
        recipient: Union[EmailRecipient, PhoneNumber],
        code: str,
        channel: OtpChannel = OtpChannel.EMAIL,
) -> bool:
    """Deliver *code*, returning whether dispatch completed.

    Never raises: delivery is best-effort because the code is already stored, and a transient
    failure is recorded RETRYING and re-driven, so failing the customer's request over it would
    turn a recoverable hiccup into a dead end. Reporting the outcome is what lets the caller be
    honest about a code that is not coming.
    """
    from main.app.domain.user.user_messages import AccountSecurityMessages
    account_security_messages = di[AccountSecurityMessages]

    # The code is useless (or stale — resends overwrite it) past its validity, so
    # cap delivery retries at the OTP window instead of the full retry ladder.
    expires_at = Utils.datetime_now() + OTP_TTL

    try:
        if channel == OtpChannel.WHATSAPP:
            # PRD §26.4.4: WhatsApp account linking delivers its code over WhatsApp itself,
            # using the §26.7 `otp_auth` template, and falls back to SMS on the same number
            # (D60, amending D46). The code is stored under the WHATSAPP channel key
            # either way, so verification is unaffected by which transport carried it.
            return await _send_whatsapp_otp_with_sms_fallback(
                account_security_messages, recipient, code, expires_at
            )
        elif isinstance(recipient, EmailRecipient):
            firstname, _, lastname = Utils.parse_fullname(str(recipient.fullname))

            return _dispatch_completed(await account_security_messages.send_direct_email_verification_message(
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
            ))
        else:
            return _dispatch_completed(await account_security_messages.send_direct_phone_verification_message(
                recipient=MessageRequestRecipient(
                    phone=recipient
                ),
                context={
                    MessageContext.OTP: code,
                    MessageContext.VALIDITY: _validity_label(),
                },
                expires_at=expires_at
            ))
    except Exception as e:
        logger.warning("OTP delivery failed for {} via {}: {}", recipient, channel.value, e)
        return False


async def _send_whatsapp_otp_with_sms_fallback(
        account_security_messages,
        recipient: PhoneNumber,
        code: str,
        expires_at: datetime,
) -> bool:
    """Deliver an account-linking OTP over WhatsApp, falling back to SMS (§26.4.4, D60).

    WhatsApp is the primary transport because the number being linked *is* a WhatsApp
    number, so a code that arrives there is the most direct proof of control. But a
    WhatsApp send can fail for reasons that have nothing to do with the customer — an
    unapproved template, a Meta outage, a number with no WhatsApp account — and a linking
    flow that dead-ends on any of those strands somebody who did nothing wrong.

    SMS to the same number is the fallback §26.4.4 names. The provider chain is the
    messaging router's existing one (Termii → Twilio for +234, the mock provider in
    dev/test), so this needs no new provider decision — which is the blocker D46 deferred
    on, and which the router had already settled.

    The fallback is deliberately **not** silent: a customer who received the code by SMS
    got the experience the PRD's second choice describes, and that is worth seeing in the
    logs when diagnosing why linking rates differ from send counts.
    """
    context = {MessageContext.OTP: code, MessageContext.VALIDITY: _validity_label()}
    try:
        return _dispatch_completed(
            await account_security_messages.send_whatsapp_link_verification_message(
                recipient=MessageRequestRecipient(phone=recipient),
                context=context,
                expires_at=expires_at,
            )
        )
    except Exception as e:
        logger.warning(
            "WhatsApp OTP delivery failed for {}; falling back to SMS (§26.4.4): {}",
            recipient.international_number, e,
        )

    return _dispatch_completed(
        await account_security_messages.send_direct_phone_verification_message(
            recipient=MessageRequestRecipient(phone=recipient),
            context=context,
            expires_at=expires_at,
        )
    )

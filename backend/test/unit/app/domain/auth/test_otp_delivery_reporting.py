"""A code request must report whether the code is actually on its way.

Delivery stays best-effort — the code is stored before dispatch, and a transient failure is
recorded RETRYING and re-driven, so a failed send must never fail the customer's request. But
`send_bulk` *buckets* failures rather than raising, so an all-channels-failed dispatch returned
normally and looked exactly like a success: the UI opened an OTP entry box for a code that was
never going to arrive. `send_verification_msg` now reports the outcome so callers can be honest.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from kink import di

from main.app.domain.user.auth.models import OtpChannel
from main.app.domain.user.auth.otp_service import (
    OTP_TTL,
    OtpService,
    send_verification_msg,
)
from main.app.domain.user.user_messages import AccountSecurityMessages
from main.appodus_utils.integrations.messaging.models import EmailRecipient
from main.appodus_utils.integrations.messaging.service import BulkSendResult

_RECIPIENT = EmailRecipient(email="user@example.com", fullname="Ada QA")


def _dispatch(successes: int, failures: int = 0) -> BulkSendResult:
    return BulkSendResult(
        total=successes + failures,
        processing_time=0.01,
        successes=[SimpleNamespace() for _ in range(successes)],
        failures=[RuntimeError("smtp down") for _ in range(failures)],
    )


async def _send_with(email_outcome) -> bool:
    """Run send_verification_msg against a sender whose dispatch yields *email_outcome*."""
    sender = AsyncMock(spec=AccountSecurityMessages)
    if isinstance(email_outcome, Exception):
        sender.send_direct_email_verification_message.side_effect = email_outcome
    else:
        sender.send_direct_email_verification_message.return_value = email_outcome

    original = di[AccountSecurityMessages]
    di[AccountSecurityMessages] = sender
    try:
        return await send_verification_msg(
            recipient=_RECIPIENT, code="654123", channel=OtpChannel.EMAIL,
        )
    finally:
        di[AccountSecurityMessages] = original


class TestDeliveryReporting:
    async def test_a_delivered_code_reports_true(self):
        assert await _send_with(_dispatch(successes=1)) is True

    async def test_a_dispatch_that_failed_on_every_channel_reports_false(self):
        # The case that was invisible: send_bulk returns normally with the failure bucketed.
        assert await _send_with(_dispatch(successes=0, failures=1)) is False

    async def test_a_raising_send_reports_false_without_propagating(self):
        # Best-effort is preserved: the customer's request must not fail over delivery.
        assert await _send_with(RuntimeError("provider exploded")) is False

    async def test_nothing_dispatched_reports_false(self):
        # None means no usable channel, or outbound messaging disabled.
        assert await _send_with(None) is False


class TestSendOtpResult:
    @staticmethod
    def _service() -> OtpService:
        svc = object.__new__(OtpService)
        svc._kv = AsyncMock()
        svc._kv.get = AsyncMock(return_value=None)
        # First send in the window: the atomic resend counter reserves slot 1.
        svc._kv.incr = AsyncMock(return_value=1)
        svc._session_service = AsyncMock()
        return svc

    @pytest.mark.parametrize("delivered", [True, False])
    async def test_send_otp_passes_the_delivery_outcome_through(self, monkeypatch, delivered):
        monkeypatch.setattr(
            "main.app.domain.user.auth.otp_service.send_verification_msg",
            AsyncMock(return_value=delivered),
        )
        svc = self._service()

        result = await svc.send_otp(OtpChannel.EMAIL, _RECIPIENT)

        assert result.delivered is delivered
        assert result.resend_in == int(OTP_TTL.total_seconds())

    async def test_the_code_is_stored_even_when_delivery_fails(self, monkeypatch):
        # The stored code is why a failed send is recoverable rather than fatal: a resend, or the
        # retry ladder, can still carry the same code to the customer.
        monkeypatch.setattr(
            "main.app.domain.user.auth.otp_service.send_verification_msg",
            AsyncMock(return_value=False),
        )
        svc = self._service()

        await svc.send_otp(OtpChannel.EMAIL, _RECIPIENT)

        assert svc._kv.set.await_count >= 1

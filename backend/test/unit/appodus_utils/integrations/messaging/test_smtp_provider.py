"""SmtpEmailProvider dispatch contract.

The drive-through's messaging_retry stage takes the SMTP host down mid-run, so the
provider must never open an unbounded socket: a host that accepts but blackholes the
connection would otherwise pin the worker thread forever and the HTTP request that
triggered the send (password reset, OTP) would never return. A bounded connect/read
timeout turns that into an ordinary transient failure the retry ladder can carry.
"""
from unittest.mock import MagicMock, patch

import pytest

from main.app.config.settings import settings
from main.app.domain.message.models import UpsertMessageDto
from main.appodus_utils.integrations.messaging.models import (
    EmailPayloadRequest,
    MessageChannel,
    MessageRecipient,
    MessageRequest,
    MessageStatus,
)
from main.appodus_utils.integrations.messaging.providers.email.smtp import SmtpEmailProvider


def _email_message() -> UpsertMessageDto:
    return UpsertMessageDto.from_request(
        MessageRequest(
            channel=MessageChannel.EMAIL,
            to=MessageRecipient(recipient="user@example.com", fullname="Ada QA"),
            payload=EmailPayloadRequest(subject="Hello", html="<p>Hi</p>", text="Hi"),
            extras={"user_id": "u-1"},
        )
    )


async def test_send_message_bounds_the_smtp_socket_with_a_timeout():
    provider = SmtpEmailProvider()

    with patch(
        "main.appodus_utils.integrations.messaging.providers.email.smtp.smtplib.SMTP"
    ) as smtp_cls:
        smtp_cls.return_value.__enter__.return_value = MagicMock()
        result = await provider.send_message(_email_message())

    _, kwargs = smtp_cls.call_args
    assert kwargs["timeout"] == settings.SMTP_TIMEOUT_SECONDS
    assert settings.SMTP_TIMEOUT_SECONDS > 0
    assert result.status == MessageStatus.SENT


async def test_send_message_propagates_a_socket_timeout_as_a_transient_failure():
    """A dead SMTP host surfaces as an exception — MessagingService then schedules a retry."""
    provider = SmtpEmailProvider()

    with patch(
        "main.appodus_utils.integrations.messaging.providers.email.smtp.smtplib.SMTP",
        side_effect=TimeoutError("timed out"),
    ):
        with pytest.raises(TimeoutError):
            await provider.send_message(_email_message())

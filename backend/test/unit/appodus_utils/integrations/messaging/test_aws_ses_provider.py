"""AmazonSESEmailProvider dispatch contract.

SES is the last-resort fallback in the email chain (Resend -> Mailjet -> AWS SES);
previously the class existed but was never imported into providers/__init__.py, so
it was never registered with the router and never exercised. These tests cover it
now that it's reachable.
"""
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from main.app.domain.message.models import UpsertMessageDto
from main.appodus_utils.integrations.exception.exceptions import (
    IntegrationAuthenticationException,
    IntegrationException,
    IntegrationRateLimitException,
)
from main.appodus_utils.integrations.messaging.models import (
    EmailPayloadRequest,
    MessageChannel,
    MessageProviderName,
    MessageRecipient,
    MessageRequest,
    MessageStatus,
)
from main.appodus_utils.integrations.messaging.providers.email.aws_ses import AmazonSESEmailProvider


def _email_message() -> UpsertMessageDto:
    return UpsertMessageDto.from_request(
        MessageRequest(
            channel=MessageChannel.EMAIL,
            to=MessageRecipient(recipient="user@example.com", fullname="Ada QA"),
            payload=EmailPayloadRequest(subject="Hello", html="<p>Hi</p>", text="Hi"),
            extras={"user_id": "u-1"},
        )
    )


def _provider() -> AmazonSESEmailProvider:
    provider = AmazonSESEmailProvider()
    provider.ses = MagicMock()
    return provider


def _client_error(code: str, message: str = "boom") -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": message}}, "SendEmail")


async def test_send_message_succeeds_and_records_provider_id():
    provider = _provider()
    provider.ses.send_email.return_value = {"MessageId": "ses-msg-1"}

    result = await provider.send_message(_email_message())

    assert result.status == MessageStatus.SENT
    assert result.provider == MessageProviderName.AWS_SES
    assert result.provider_id == "ses-msg-1"


@pytest.mark.parametrize("code", ["InvalidClientTokenId", "AuthFailure", "InvalidSignatureException"])
async def test_send_message_maps_auth_errors(code):
    provider = _provider()
    provider.ses.send_email.side_effect = _client_error(code)

    with pytest.raises(IntegrationAuthenticationException):
        await provider.send_message(_email_message())


async def test_send_message_maps_rate_limit_error():
    provider = _provider()
    provider.ses.send_email.side_effect = _client_error("TooManyRequestsException")

    with pytest.raises(IntegrationRateLimitException) as exc_info:
        await provider.send_message(_email_message())

    assert exc_info.value.key == "user@example.com"


async def test_send_message_maps_other_client_errors():
    provider = _provider()
    provider.ses.send_email.side_effect = _client_error("MessageRejected", "content rejected")

    with pytest.raises(IntegrationException, match="content rejected"):
        await provider.send_message(_email_message())


async def test_get_message_status_returns_sending_status():
    provider = _provider()
    provider.ses.get_message_insights.return_value = {"SendingStatus": "SUCCESS"}

    status = await provider.get_message_status("ses-msg-1")

    assert status == "SUCCESS"


async def test_get_message_status_swallows_client_errors():
    provider = _provider()
    provider.ses.get_message_insights.side_effect = _client_error("NotFoundException")

    status = await provider.get_message_status("ses-msg-1")

    assert status is None

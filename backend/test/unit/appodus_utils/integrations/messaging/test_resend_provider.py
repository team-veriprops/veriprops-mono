"""ResendEmailProvider dispatch contract — the prod/staging primary email provider.

Mirrors the Mailjet-shaped HTTP provider pattern: an httpx.AsyncClient POST, mapped
error codes, and a bookkeeping DTO mutation on success.
"""
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from main.app.domain.message.models import UpsertMessageDto
from main.appodus_utils.integrations.exception.exceptions import (
    IntegrationAuthenticationException,
    IntegrationException,
    IntegrationRateLimitException,
)
from main.appodus_utils.integrations.messaging.models import (
    Attachment,
    EmailPayloadRequest,
    MessageChannel,
    MessageProviderName,
    MessageRecipient,
    MessageRequest,
    MessageStatus,
)
from main.appodus_utils.integrations.messaging.providers.email.resend import ResendEmailProvider


def _email_message(**payload_kwargs) -> UpsertMessageDto:
    payload_kwargs.setdefault("subject", "Hello")
    payload_kwargs.setdefault("html", "<p>Hi</p>")
    payload_kwargs.setdefault("text", "Hi")
    return UpsertMessageDto.from_request(
        MessageRequest(
            channel=MessageChannel.EMAIL,
            to=MessageRecipient(recipient="user@example.com", fullname="Ada QA"),
            payload=EmailPayloadRequest(**payload_kwargs),
            extras={"user_id": "u-1"},
        )
    )


def _provider() -> ResendEmailProvider:
    provider = ResendEmailProvider()
    provider.client = AsyncMock()
    return provider


def _response(status_code: int, json_body: dict | None = None, headers: dict | None = None) -> MagicMock:
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.headers = headers or {}
    response.text = "" if json_body is None else "body"
    response.json.return_value = json_body or {}
    if status_code >= 500:
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "server error", request=MagicMock(), response=response
        )
    return response


async def test_send_message_succeeds_and_records_provider_id():
    provider = _provider()
    provider.client.post.return_value = _response(200, {"id": "resend-msg-1"})

    result = await provider.send_message(_email_message())

    assert result.status == MessageStatus.SENT
    assert result.provider == MessageProviderName.RESEND
    assert result.provider_id == "resend-msg-1"

    url, kwargs = provider.client.post.call_args
    assert url[0] == f"{provider.BASE_URL}/emails"
    assert kwargs["headers"]["Authorization"] == f"Bearer {provider.api_key}"
    body = kwargs["json"]
    assert body["to"] == ["user@example.com"]
    assert body["subject"] == "Hello"
    assert body["html"] == "<p>Hi</p>"
    assert body["text"] == "Hi"


async def test_send_message_includes_attachments():
    provider = _provider()
    provider.client.post.return_value = _response(200, {"id": "resend-msg-2"})
    attachment = Attachment(filename="doc.pdf", content="ZmFrZQ==", content_type="application/pdf")

    await provider.send_message(_email_message(attachments=[attachment]))

    body = provider.client.post.call_args.kwargs["json"]
    assert body["attachments"] == [
        {"filename": "doc.pdf", "content": "ZmFrZQ==", "content_type": "application/pdf"}
    ]


@pytest.mark.parametrize("status_code", [401, 403])
async def test_send_message_maps_auth_errors(status_code):
    provider = _provider()
    provider.client.post.return_value = _response(status_code, {"message": "bad key"})

    with pytest.raises(IntegrationAuthenticationException):
        await provider.send_message(_email_message())


async def test_send_message_maps_rate_limit_with_retry_after_header():
    provider = _provider()
    provider.client.post.return_value = _response(429, {"message": "slow down"}, headers={"retry-after": "30"})

    with pytest.raises(IntegrationRateLimitException) as exc_info:
        await provider.send_message(_email_message())

    assert exc_info.value.key == "user@example.com"


async def test_send_message_maps_validation_error():
    provider = _provider()
    provider.client.post.return_value = _response(422, {"message": "invalid recipient"})

    with pytest.raises(IntegrationException, match="invalid recipient"):
        await provider.send_message(_email_message())


async def test_send_message_propagates_server_errors():
    provider = _provider()
    provider.client.post.return_value = _response(500)

    with pytest.raises(httpx.HTTPStatusError):
        await provider.send_message(_email_message())


async def test_get_message_status_returns_last_event():
    provider = _provider()
    provider.client.get.return_value = _response(200, {"last_event": "delivered"})

    status = await provider.get_message_status("resend-msg-1")

    assert status == "delivered"


async def test_get_message_status_swallows_failures():
    provider = _provider()
    provider.client.get.side_effect = httpx.ConnectError("boom")

    status = await provider.get_message_status("resend-msg-1")

    assert status is None

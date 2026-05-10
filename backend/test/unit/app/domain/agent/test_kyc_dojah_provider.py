"""Unit tests for DojahKycProvider (S8 — R3.2).

All HTTP calls are intercepted via pytest-httpx or unittest.mock so no real
network traffic is made. Tests verify:
- BVN success path → BvnVerificationResult(verified=True)
- BVN failure path → BvnVerificationResult(verified=False)
- BVN HTTP 4xx → IntegrationException
- BVN timeout → IntegrationException
- submit_selfie success → returns verification_id string
- submit_selfie HTTP error → IntegrationException
"""
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from main.app.domain.user.agent.kyc.providers.dojah import DojahKycProvider
from main.appodus_utils.integrations.exception.exceptions import IntegrationException


def _mock_response(status_code: int, json_body: dict) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_body
    resp.text = str(json_body)
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=resp
        )
    else:
        resp.raise_for_status.return_value = None
    return resp


async def test_verify_bvn_success():
    provider = DojahKycProvider()
    body = {"entity": {"bvn": "22222222222", "reference_id": "dj-ref-001", "verified": True}}
    mock_resp = _mock_response(200, body)

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        result = await provider.verify_bvn("22222222222")

    assert result.verified is True
    assert result.verification_id == "dj-ref-001"
    assert result.provider == "dojah"
    assert result.failure_reason is None


async def test_verify_bvn_failure():
    provider = DojahKycProvider()
    body = {"entity": {}, "error": "BVN not found"}
    mock_resp = _mock_response(200, body)

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        result = await provider.verify_bvn("11111111111")

    assert result.verified is False
    assert result.failure_reason == "BVN not found"
    assert result.provider == "dojah"


async def test_verify_bvn_http_error():
    provider = DojahKycProvider()
    mock_resp = _mock_response(401, {"error": "Unauthorized"})

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        with pytest.raises(IntegrationException) as exc_info:
            await provider.verify_bvn("22222222222")
        assert "401" in exc_info.value.message


async def test_verify_bvn_timeout():
    provider = DojahKycProvider()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
        mock_client_cls.return_value = mock_client

        with pytest.raises(IntegrationException) as exc_info:
            await provider.verify_bvn("22222222222")
        assert "timed out" in exc_info.value.message


async def test_submit_selfie_returns_verification_id():
    provider = DojahKycProvider()
    body = {"entity": {"verification_id": "selfie-job-xyz"}}
    mock_resp = _mock_response(200, body)

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        job_id = await provider.submit_selfie(b"\x00\x01\x02", reference_bvn_last4="1234")

    assert job_id == "selfie-job-xyz"


async def test_submit_selfie_http_error():
    provider = DojahKycProvider()
    mock_resp = _mock_response(400, {"error": "Bad request"})

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        with pytest.raises(IntegrationException) as exc_info:
            await provider.submit_selfie(b"\x00")
        assert "400" in exc_info.value.message

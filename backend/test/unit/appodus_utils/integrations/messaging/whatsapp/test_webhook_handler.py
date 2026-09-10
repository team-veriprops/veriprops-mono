"""Meta webhook receiver (PRD §26.3.3, WA-09) — the channel's public front door.

This endpoint is unauthenticated by design: the HMAC signature over the raw body *is*
the authentication, so the tests below are the access-control tests for the whole
inbound path. They also pin the availability behaviour Meta requires — an acknowledged
delivery, even when our own downstream work fails, so a transient bug cannot turn into a
retry storm or a disabled subscription.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from unittest.mock import AsyncMock

import pytest

from main.app.config.settings import IntegratedPlatform, settings
from main.appodus_utils.config.settings import SECRET_PLACEHOLDER
from main.appodus_utils.exception.exceptions import UnauthorizedException
from main.appodus_utils.integrations.messaging.providers.whatsapp.webhook import (
    WhatsAppWebhookHandler,
)

APP_SECRET = "test-app-secret"
VERIFY_TOKEN = "test-verify-token"

BODY = json.dumps({
    "object": "whatsapp_business_account",
    "entry": [{"id": "WABA", "changes": [{"field": "messages", "value": {
        "messaging_product": "whatsapp",
        "metadata": {"phone_number_id": "PNID"},
        "messages": [{
            "from": "2348012345678", "id": "wamid.A1", "timestamp": "1756600000",
            "type": "text", "text": {"body": "Hello"},
        }],
    }}]}],
}).encode()


def sign(body: bytes, secret: str = APP_SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@pytest.fixture
def handler(monkeypatch):
    monkeypatch.setattr(settings, "WHATSAPP_APP_SECRET_KEY", APP_SECRET)
    monkeypatch.setattr(settings, "WHATSAPP_BUSINESS_WEBHOOK_VERIFY_TOKEN", VERIFY_TOKEN)
    h = WhatsAppWebhookHandler()
    h.platform_secret = APP_SECRET
    h._inbound_service = AsyncMock()
    return h


class TestPlatformWiring:
    def test_serves_the_whatsapp_platform_route(self, handler):
        assert handler.platform == IntegratedPlatform.WHATSAPP


class TestSignatureVerification:
    async def test_accepts_a_correctly_signed_body(self, handler):
        assert await handler.validate_signature(BODY, {"x-hub-signature-256": sign(BODY)})

    async def test_rejects_a_tampered_body(self, handler):
        # The signature covers the raw bytes; re-serializing or editing must not verify.
        tampered = BODY.replace(b"Hello", b"HELLO")
        assert not await handler.validate_signature(tampered, {"x-hub-signature-256": sign(BODY)})

    async def test_rejects_a_signature_made_with_another_secret(self, handler):
        assert not await handler.validate_signature(
            BODY, {"x-hub-signature-256": sign(BODY, "wrong-secret")}
        )

    async def test_rejects_a_missing_signature(self, handler):
        assert not await handler.validate_signature(BODY, {})

    async def test_rejects_a_malformed_signature_header(self, handler):
        for header in ("", "sha256=", "not-a-signature", sign(BODY).removeprefix("sha256=")):
            assert not await handler.validate_signature(BODY, {"x-hub-signature-256": header})

    async def test_finds_the_header_whatever_its_casing(self, handler):
        assert await handler.validate_signature(BODY, {"X-Hub-Signature-256": sign(BODY)})

    async def test_fails_closed_when_no_secret_is_configured(self, handler, monkeypatch):
        # An unconfigured secret must never mean "accept anything".
        for absent in ("", SECRET_PLACEHOLDER):
            handler.platform_secret = absent
            assert not await handler.validate_signature(BODY, {"x-hub-signature-256": sign(BODY)})

    async def test_an_unsigned_delivery_is_refused_end_to_end(self, handler):
        with pytest.raises(UnauthorizedException):
            await handler.handle_webhook(BODY, {})
        handler._inbound_service.ingest.assert_not_awaited()


class TestSubscriptionHandshake:
    async def test_echoes_the_challenge_for_the_configured_verify_token(self, handler):
        challenge = await handler._process_verify_webhook_payload(
            {"hub.mode": "subscribe", "hub.verify_token": VERIFY_TOKEN, "hub.challenge": "1158201444"}
        )
        # Meta requires the challenge echoed verbatim.
        assert challenge == "1158201444"

    async def test_refuses_a_wrong_verify_token(self, handler):
        with pytest.raises(UnauthorizedException):
            await handler._process_verify_webhook_payload(
                {"hub.mode": "subscribe", "hub.verify_token": "guess", "hub.challenge": "x"}
            )

    async def test_refuses_a_non_subscribe_mode(self, handler):
        with pytest.raises(UnauthorizedException):
            await handler._process_verify_webhook_payload(
                {"hub.mode": "unsubscribe", "hub.verify_token": VERIFY_TOKEN, "hub.challenge": "x"}
            )

    async def test_refuses_the_handshake_when_no_verify_token_is_configured(self, handler, monkeypatch):
        monkeypatch.setattr(settings, "WHATSAPP_BUSINESS_WEBHOOK_VERIFY_TOKEN", SECRET_PLACEHOLDER)
        with pytest.raises(UnauthorizedException):
            await handler._process_verify_webhook_payload(
                {"hub.mode": "subscribe", "hub.verify_token": SECRET_PLACEHOLDER, "hub.challenge": "x"}
            )


class TestDelivery:
    async def test_hands_each_normalized_message_to_the_inbound_service(self, handler):
        await handler.handle_webhook(BODY, {"x-hub-signature-256": sign(BODY)})
        handler._inbound_service.ingest.assert_awaited_once()
        [message] = handler._inbound_service.ingest.await_args.args
        assert message.wamid == "wamid.A1"
        assert message.from_phone == "+2348012345678"

    async def test_acknowledges_a_delivery_receipt_without_ingesting(self, handler):
        body = json.dumps({"entry": [{"changes": [{"field": "messages", "value": {
            "statuses": [{"id": "wamid.OUT", "status": "read"}]}}]}]}).encode()
        await handler.handle_webhook(body, {"x-hub-signature-256": sign(body)})
        handler._inbound_service.ingest.assert_not_awaited()

    async def test_a_downstream_failure_still_acknowledges_the_delivery(self, handler):
        # Meta retries — then throttles, then disables the subscription — on a non-2xx.
        # Our own bug must not cost us the channel; the wamid dedup makes it safe.
        handler._inbound_service.ingest.side_effect = RuntimeError("db down")
        await handler.handle_webhook(BODY, {"x-hub-signature-256": sign(BODY)})
        handler._inbound_service.ingest.assert_awaited_once()

    async def test_a_malformed_signed_body_is_acknowledged_and_ignored(self, handler):
        body = b"{not json"
        await handler.handle_webhook(body, {"x-hub-signature-256": sign(body)})
        handler._inbound_service.ingest.assert_not_awaited()

    async def test_one_failing_message_does_not_block_the_next(self, handler):
        second = json.loads(BODY)
        second["entry"][0]["changes"][0]["value"]["messages"].append({
            "from": "2348012345678", "id": "wamid.A2", "timestamp": "1756600001",
            "type": "text", "text": {"body": "Second"},
        })
        body = json.dumps(second).encode()
        handler._inbound_service.ingest.side_effect = [RuntimeError("boom"), None]
        await handler.handle_webhook(body, {"x-hub-signature-256": sign(body)})
        assert handler._inbound_service.ingest.await_count == 2

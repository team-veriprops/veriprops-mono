"""Payment-gateway webhooks: who may call them, and what each event does.

Signatures follow each provider's documented scheme:

* **Flutterwave v3** sends the secret hash configured on the dashboard, verbatim, in
  `verif-hash`; it is compared directly (it is not an HMAC of the body).
* **Paystack** signs the raw body with HMAC-SHA512 keyed by the account's **secret key**, in
  `x-paystack-signature`; there is no separate webhook secret.

Both fail closed: an unconfigured secret rejects every request. A verified event is never
trusted on its own word either — a charge event only asks `PaymentService` to confirm the
charge with the gateway. Events we do not act on are acknowledged, so the provider stops
retrying them.
"""
import hashlib
import hmac
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.config.settings import IntegratedPlatform, settings
from main.appodus_utils.config.settings import SECRET_PLACEHOLDER
from main.appodus_utils.integrations.payment.gateway.flutterwave.webhook import FlutterwaveWebhookHandler
from main.appodus_utils.integrations.payment.gateway.paystack.webhook import PaystackWebhookHandler

FLW_HASH = "flw-dashboard-secret-hash"
PSK_KEY = "sk_test_abc"


def _body(payload: dict) -> bytes:
    return json.dumps(payload).encode()


def _psk_signature(body: bytes, key: str = PSK_KEY) -> str:
    return hmac.new(key.encode(), body, hashlib.sha512).hexdigest()


@pytest.fixture
def payments(monkeypatch):
    service = MagicMock()
    service.confirm_from_gateway = AsyncMock(return_value=True)
    service.record_chargeback = AsyncMock(return_value=None)
    monkeypatch.setattr(FlutterwaveWebhookHandler, "_payments", staticmethod(lambda: service))
    monkeypatch.setattr(PaystackWebhookHandler, "_payments", staticmethod(lambda: service))
    return service


def _flutterwave() -> FlutterwaveWebhookHandler:
    return FlutterwaveWebhookHandler(callback_service=MagicMock())


def _paystack() -> PaystackWebhookHandler:
    return PaystackWebhookHandler(callback_service=MagicMock())


class TestFlutterwaveSignature:
    @pytest.fixture(autouse=True)
    def secret(self, monkeypatch):
        monkeypatch.setattr(settings, "FLUTTERWAVE_WEBHOOK_SECRET", FLW_HASH)

    async def test_the_dashboard_hash_verbatim_is_accepted(self):
        assert await _flutterwave().validate_signature(b"{}", {"verif-hash": FLW_HASH}) is True

    @pytest.mark.parametrize("headers", [
        {"verif-hash": "wrong"},
        {"verif-hash": hmac.new(FLW_HASH.encode(), b"{}", hashlib.sha256).hexdigest()},  # the old, wrong scheme
        {},
    ])
    async def test_anything_else_is_rejected(self, headers):
        assert await _flutterwave().validate_signature(b"{}", headers) is False

    @pytest.mark.parametrize("configured", [None, "", SECRET_PLACEHOLDER])
    async def test_an_unconfigured_secret_rejects_everything(self, monkeypatch, configured):
        monkeypatch.setattr(settings, "FLUTTERWAVE_WEBHOOK_SECRET", configured)
        assert await _flutterwave().validate_signature(b"{}", {"verif-hash": configured or ""}) is False


class TestPaystackSignature:
    @pytest.fixture(autouse=True)
    def key(self, monkeypatch):
        monkeypatch.setattr(settings, "PAYSTACK_SECRET_KEY", PSK_KEY)

    async def test_an_hmac_sha512_of_the_raw_body_with_the_secret_key_is_accepted(self):
        body = _body({"event": "charge.success"})
        assert await _paystack().validate_signature(body, {"x-paystack-signature": _psk_signature(body)}) is True

    @pytest.mark.parametrize("signed_with", ["another-key"])
    async def test_a_signature_from_another_key_is_rejected(self, signed_with):
        body = _body({"event": "charge.success"})
        headers = {"x-paystack-signature": _psk_signature(body, signed_with)}
        assert await _paystack().validate_signature(body, headers) is False

    async def test_a_tampered_body_is_rejected(self):
        body = _body({"event": "charge.success"})
        headers = {"x-paystack-signature": _psk_signature(body)}
        assert await _paystack().validate_signature(body + b" ", headers) is False

    @pytest.mark.parametrize("configured", ["", SECRET_PLACEHOLDER])
    async def test_an_unconfigured_key_rejects_everything(self, monkeypatch, configured):
        monkeypatch.setattr(settings, "PAYSTACK_SECRET_KEY", configured)
        body = _body({"event": "charge.success"})
        assert await _paystack().validate_signature(body, {"x-paystack-signature": _psk_signature(body, configured or "x")}) is False


class TestFlutterwaveEvents:
    async def test_a_completed_charge_asks_for_confirmation_with_the_gateway(self, payments):
        await _flutterwave()._process_handle_webhook_payload({
            "event": "charge.completed",
            "data": {"id": 3091255, "tx_ref": "ref-1", "flw_ref": "FLW-1", "status": "successful", "amount": 10},
        })
        payments.confirm_from_gateway.assert_awaited_once_with("ref-1")

    async def test_a_failed_charge_is_confirmed_too_so_the_failure_is_recorded(self, payments):
        await _flutterwave()._process_handle_webhook_payload({
            "event": "charge.completed", "data": {"id": 1, "tx_ref": "ref-1", "status": "failed"},
        })
        payments.confirm_from_gateway.assert_awaited_once_with("ref-1")

    async def test_a_chargeback_is_matched_by_the_gateways_reference(self, payments):
        await _flutterwave()._process_handle_webhook_payload({
            "event": "chargeback.initiated",
            "data": {"id": 42, "flw_ref": "FLW-1", "amount": 10, "comment": "Card holder disputes", "status": "initiated"},
        })
        payments.record_chargeback.assert_awaited_once_with(
            IntegratedPlatform.FLUTTERWAVE, event_id="flutterwave:chargeback:42",
            gateway_reference="FLW-1", reason="Card holder disputes",
        )

    @pytest.mark.parametrize("event", ["transfer.completed", "refund.completed", "something.new"])
    async def test_events_we_do_not_act_on_are_acknowledged(self, payments, event):
        result = await _flutterwave()._process_handle_webhook_payload({"event": event, "data": {"id": 1}})
        assert result == {"status": "ignored"}
        payments.confirm_from_gateway.assert_not_awaited()


class TestPaystackEvents:
    async def test_a_successful_charge_asks_for_confirmation_with_the_gateway(self, payments):
        await _paystack()._process_handle_webhook_payload({
            "event": "charge.success", "data": {"id": 1, "reference": "ref-1", "status": "success"},
        })
        payments.confirm_from_gateway.assert_awaited_once_with("ref-1")

    async def test_a_dispute_is_matched_by_our_reference(self, payments):
        await _paystack()._process_handle_webhook_payload({
            "event": "charge.dispute.create",
            "data": {"id": 77, "category": "fraud", "transaction": {"id": 1, "reference": "ref-1"}},
        })
        payments.record_chargeback.assert_awaited_once_with(
            IntegratedPlatform.PAYSTACK, event_id="paystack:dispute:77", tx_ref="ref-1", reason="fraud",
        )

    @pytest.mark.parametrize("event", ["transfer.success", "refund.processed", "subscription.create", "something.new"])
    async def test_events_we_do_not_act_on_are_acknowledged(self, payments, event):
        result = await _paystack()._process_handle_webhook_payload({"event": event, "data": {}})
        assert result == {"status": "ignored"}
        payments.confirm_from_gateway.assert_not_awaited()

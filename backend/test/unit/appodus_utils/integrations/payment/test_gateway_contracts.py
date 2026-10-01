"""Live payment-gateway contracts, pinned against each provider's documented HTTP shapes.

CI and e2e never reach a gateway (PAYMENT_STUB_MODE), so these respx tests are what hold the
live adapters to the requests Flutterwave v3 and Paystack actually accept, and to how their
answers are normalised into one `GatewayCharge`:

* amounts travel in **minor units** everywhere inside Veriprops; Flutterwave speaks major
  units, Paystack speaks kobo;
* a charge is looked up by **our** reference (`tx_ref`), never by the gateway's id;
* a gateway failure surfaces as an `IntegrationException`, with the provider's own text kept
  out of it.
"""
import json

import httpx
import pytest
import respx

from main.app.config.settings import settings
from main.appodus_utils.db.types.money import TransactionCurrency
from main.appodus_utils.integrations.exception.exceptions import IntegrationException
from main.appodus_utils.integrations.payment.gateway.flutterwave.payment import FlutterwavePaymentGateway
from main.appodus_utils.integrations.payment.gateway.models import (
    GatewayChargeStatus,
    HostedCheckoutRequest,
)
from main.appodus_utils.integrations.payment.gateway.paystack.payment import PaystackPaymentGateway

FLW = "https://api.flutterwave.test/v3"
PSK = "https://api.paystack.test"


@pytest.fixture(autouse=True)
def gateway_settings(monkeypatch):
    monkeypatch.setattr(settings, "FLUTTERWAVE_BASE_URL", FLW)
    monkeypatch.setattr(settings, "FLUTTERWAVE_SECRET_KEY", "FLWSECK_TEST-abc")
    monkeypatch.setattr(settings, "PAYSTACK_BASE_URL", PSK)
    monkeypatch.setattr(settings, "PAYSTACK_SECRET_KEY", "sk_test_abc")


def _checkout(**over) -> HostedCheckoutRequest:
    base = dict(
        reference="VP-2026-ABC123-x1y2z3w4",
        amount_minor=12_000_050,
        currency=TransactionCurrency.NGN,
        redirect_url="https://veriprops.ng/portal/verifications/ver-1/pay",
        customer_email="ada@example.com",
        customer_phone="+2348031234567",
        customer_name="Ada Obi",
        title="Veriprops verification",
        description="STANDARD verification VP-2026-ABC123",
    )
    base.update(over)
    return HostedCheckoutRequest(**base)


# ─── Flutterwave v3 ──────────────────────────────────────────────


class TestFlutterwave:
    @respx.mock
    async def test_hosted_checkout_sends_major_units_and_returns_the_link(self):
        route = respx.post(f"{FLW}/payments").mock(return_value=httpx.Response(
            200, json={"status": "success", "message": "Hosted Link", "data": {"link": "https://checkout.flutterwave.com/v3/hosted/pay/abc"}},
        ))

        url = await FlutterwavePaymentGateway().create_hosted_checkout(_checkout())

        assert url == "https://checkout.flutterwave.com/v3/hosted/pay/abc"
        sent = json.loads(route.calls.last.request.content)
        assert sent["tx_ref"] == "VP-2026-ABC123-x1y2z3w4"
        assert sent["amount"] == 120000.50
        assert sent["currency"] == "NGN"
        assert sent["redirect_url"] == "https://veriprops.ng/portal/verifications/ver-1/pay"
        assert sent["customer"] == {"email": "ada@example.com", "phonenumber": "+2348031234567", "name": "Ada Obi"}
        assert route.calls.last.request.headers["authorization"] == "Bearer FLWSECK_TEST-abc"

    @respx.mock
    async def test_a_charge_is_verified_by_our_reference(self):
        route = respx.get(f"{FLW}/transactions/verify_by_reference", params={"tx_ref": "ref-1"}).mock(
            return_value=httpx.Response(200, json={"status": "success", "message": "Transaction fetched successfully", "data": {
                "id": 3091255, "tx_ref": "ref-1", "flw_ref": "FLW-MOCK-1", "amount": 1500.5,
                "charged_amount": 1520.5, "currency": "NGN", "status": "successful",
            }}),
        )

        charge = await FlutterwavePaymentGateway().get_charge("ref-1")

        assert route.called
        assert charge.reference == "ref-1"
        assert charge.gateway_transaction_id == "3091255"
        assert charge.gateway_reference == "FLW-MOCK-1"
        assert charge.amount_minor == 150_050  # the amount asked for, not the fee-inclusive charged_amount
        assert charge.currency == TransactionCurrency.NGN
        assert charge.status == GatewayChargeStatus.SUCCEEDED

    @pytest.mark.parametrize("status, expected", [
        ("failed", GatewayChargeStatus.FAILED),
        ("pending", GatewayChargeStatus.PENDING),
        ("something-new", GatewayChargeStatus.PENDING),
    ])
    @respx.mock
    async def test_non_success_statuses_normalise(self, status, expected):
        respx.get(f"{FLW}/transactions/verify_by_reference").mock(return_value=httpx.Response(200, json={
            "status": "success", "message": "ok", "data": {
                "id": 1, "tx_ref": "ref-1", "flw_ref": "F", "amount": 10, "currency": "NGN", "status": status,
            }}))

        assert (await FlutterwavePaymentGateway().get_charge("ref-1")).status == expected

    @respx.mock
    async def test_a_reference_the_gateway_never_charged_is_none(self):
        respx.get(f"{FLW}/transactions/verify_by_reference").mock(return_value=httpx.Response(
            400, json={"status": "error", "message": "No transaction was found for this id", "data": None},
        ))

        assert await FlutterwavePaymentGateway().get_charge("never-paid") is None

    @respx.mock
    async def test_a_refund_targets_the_gateway_transaction_by_id(self):
        respx.get(f"{FLW}/transactions/verify_by_reference").mock(return_value=httpx.Response(200, json={
            "status": "success", "message": "ok", "data": {
                "id": 777, "tx_ref": "ref-1", "flw_ref": "F", "amount": 1500, "currency": "NGN", "status": "successful",
            }}))
        refund = respx.post(f"{FLW}/transactions/777/refund").mock(return_value=httpx.Response(
            200, json={"status": "success", "message": "Transaction refund initiated", "data": {"id": 9, "status": "pending"}},
        ))

        await FlutterwavePaymentGateway().refund_charge("ref-1", amount_minor=150_000, reason="failed verification")

        assert json.loads(refund.calls.last.request.content) == {"amount": 1500.0, "comments": "failed verification"}

    @respx.mock
    async def test_a_gateway_error_is_an_integration_failure_without_the_providers_text(self):
        respx.post(f"{FLW}/payments").mock(return_value=httpx.Response(
            401, json={"status": "error", "message": "Invalid authorization key FLWSECK_TEST-abc", "data": None},
        ))

        with pytest.raises(IntegrationException) as caught:
            await FlutterwavePaymentGateway().create_hosted_checkout(_checkout())

        assert "FLWSECK" not in str(caught.value)


# ─── Paystack ────────────────────────────────────────────────────


class TestPaystack:
    @respx.mock
    async def test_hosted_checkout_sends_kobo_and_returns_the_authorization_url(self):
        route = respx.post(f"{PSK}/transaction/initialize").mock(return_value=httpx.Response(
            200, json={"status": True, "message": "Authorization URL created", "data": {
                "authorization_url": "https://checkout.paystack.com/abc", "access_code": "abc", "reference": "VP-2026-ABC123-x1y2z3w4",
            }},
        ))

        url = await PaystackPaymentGateway().create_hosted_checkout(_checkout())

        assert url == "https://checkout.paystack.com/abc"
        sent = json.loads(route.calls.last.request.content)
        assert sent["reference"] == "VP-2026-ABC123-x1y2z3w4"
        assert sent["amount"] == 12_000_050
        assert sent["currency"] == "NGN"
        assert sent["email"] == "ada@example.com"
        assert sent["callback_url"] == "https://veriprops.ng/portal/verifications/ver-1/pay"
        assert route.calls.last.request.headers["authorization"] == "Bearer sk_test_abc"

    @pytest.mark.parametrize("status, expected", [
        ("success", GatewayChargeStatus.SUCCEEDED),
        ("failed", GatewayChargeStatus.FAILED),
        ("reversed", GatewayChargeStatus.FAILED),
        ("abandoned", GatewayChargeStatus.PENDING),
        ("ongoing", GatewayChargeStatus.PENDING),
    ])
    @respx.mock
    async def test_a_charge_is_verified_by_our_reference(self, status, expected):
        respx.get(f"{PSK}/transaction/verify/ref-1").mock(return_value=httpx.Response(200, json={
            "status": True, "message": "Verification successful", "data": {
                "id": 4099260516, "reference": "ref-1", "amount": 150_050, "currency": "NGN", "status": status,
            }}))

        charge = await PaystackPaymentGateway().get_charge("ref-1")

        assert charge.reference == "ref-1"
        assert charge.gateway_transaction_id == "4099260516"
        assert charge.gateway_reference == "4099260516"
        assert charge.amount_minor == 150_050
        assert charge.status == expected

    @respx.mock
    async def test_a_reference_the_gateway_never_saw_is_none(self):
        respx.get(f"{PSK}/transaction/verify/never").mock(return_value=httpx.Response(
            404, json={"status": False, "message": "Transaction reference not found"},
        ))

        assert await PaystackPaymentGateway().get_charge("never") is None

    @respx.mock
    async def test_a_refund_names_the_transaction_by_our_reference_in_kobo(self):
        route = respx.post(f"{PSK}/refund").mock(return_value=httpx.Response(200, json={
            "status": True, "message": "Refund has been queued for processing", "data": {"status": "pending"},
        }))

        await PaystackPaymentGateway().refund_charge("ref-1", amount_minor=150_000, reason="failed verification")

        assert json.loads(route.calls.last.request.content) == {
            "transaction": "ref-1", "amount": 150_000, "merchant_note": "failed verification",
        }

    @respx.mock
    async def test_a_status_false_body_is_an_integration_failure(self):
        respx.post(f"{PSK}/refund").mock(return_value=httpx.Response(
            200, json={"status": False, "message": "Transaction has been fully reversed"},
        ))

        with pytest.raises(IntegrationException):
            await PaystackPaymentGateway().refund_charge("ref-1", amount_minor=1, reason=None)

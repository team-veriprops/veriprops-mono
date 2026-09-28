"""Live payout-transfer contracts, pinned against each provider's documented HTTP shapes.

Agent payouts leave through the same gateways that collect payments. CI and e2e never reach
a gateway (PAYMENT_STUB_MODE), so these respx tests hold the live adapters to what
Flutterwave v3 and Paystack actually accept, and to how their answers normalise:

* amounts are **minor units** inside Veriprops; Flutterwave speaks major units, Paystack kobo;
* a transfer is found again by **our** reference, so a lost answer can always be re-asked;
* an account name comes from the bank, never from what an agent typed;
* a gateway that answered "no" (`GatewayDeclined`) is told apart from one that could not be
  reached, because only a "no" proves no money moved.
"""
import json

import httpx
import pytest
import respx

from main.app.config.settings import settings
from main.appodus_utils.db.types.money import TransactionCurrency
from main.appodus_utils.integrations.exception.exceptions import IntegrationException
from main.appodus_utils.integrations.payment.gateway.flutterwave.payment import FlutterwavePaymentGateway
from main.appodus_utils.integrations.payment.gateway.http import GatewayDeclined
from main.appodus_utils.integrations.payment.gateway.models import (
    GatewayTransferStatus,
    TransferRequest,
)
from main.appodus_utils.integrations.payment.gateway.paystack.payment import PaystackPaymentGateway

FLW = "https://api.flutterwave.test/v3"
PSK = "https://api.paystack.test"
REF = "vp-po-0123456789abcdef0123456789abcdef-1"


@pytest.fixture(autouse=True)
def gateway_settings(monkeypatch):
    monkeypatch.setattr(settings, "FLUTTERWAVE_BASE_URL", FLW)
    monkeypatch.setattr(settings, "FLUTTERWAVE_SECRET_KEY", "FLWSECK_TEST-abc")
    monkeypatch.setattr(settings, "PAYSTACK_BASE_URL", PSK)
    monkeypatch.setattr(settings, "PAYSTACK_SECRET_KEY", "sk_test_abc")


def _transfer(**over) -> TransferRequest:
    base = dict(
        reference=REF, amount_minor=4_997_550, currency=TransactionCurrency.NGN,
        bank_code="044", account_number="0690000031", account_name="ADA OBI",
        narration="Veriprops payout",
    )
    base.update(over)
    return TransferRequest(**base)


class TestTransferRequest:
    @pytest.mark.parametrize("reference", ["short-ref", "VP-PO-UPPERCASE-0123456789", "has space in it 0123456789"])
    def test_a_reference_both_gateways_would_refuse_is_rejected_here(self, reference):
        # Paystack takes lowercase [a-z0-9_-] of at least 16 characters; Flutterwave takes that too.
        with pytest.raises(ValueError):
            _transfer(reference=reference)

    def test_a_transfer_moves_money(self):
        with pytest.raises(ValueError):
            _transfer(amount_minor=0)


# ─── Flutterwave v3 ──────────────────────────────────────────────


class TestFlutterwaveTransfers:
    @respx.mock
    async def test_banks_are_listed_for_nigeria(self):
        respx.get(f"{FLW}/banks/NG").mock(return_value=httpx.Response(200, json={
            "status": "success", "message": "Banks fetched successfully",
            "data": [{"id": 1, "code": "044", "name": "Access Bank"}, {"id": 2, "code": "058", "name": "GTBank"}],
        }))

        banks = await FlutterwavePaymentGateway().list_banks(TransactionCurrency.NGN)

        assert [(b.code, b.name) for b in banks] == [("044", "Access Bank"), ("058", "GTBank")]

    @respx.mock
    async def test_an_account_resolves_to_the_name_the_bank_holds(self):
        route = respx.post(f"{FLW}/accounts/resolve").mock(return_value=httpx.Response(200, json={
            "status": "success", "message": "Account details fetched",
            "data": {"account_number": "0690000032", "account_name": "Pastor Bright"},
        }))

        account = await FlutterwavePaymentGateway().resolve_account("044", "0690000032")

        assert json.loads(route.calls.last.request.content) == {"account_number": "0690000032", "account_bank": "044"}
        assert (account.bank_code, account.account_number, account.account_name) == ("044", "0690000032", "Pastor Bright")

    @respx.mock
    async def test_an_account_the_bank_does_not_know_resolves_to_nothing(self):
        respx.post(f"{FLW}/accounts/resolve").mock(return_value=httpx.Response(400, json={
            "status": "error", "message": "Sorry, that account number is invalid, please check and try again", "data": None,
        }))

        assert await FlutterwavePaymentGateway().resolve_account("044", "0000000000") is None

    @respx.mock
    async def test_the_fee_is_quoted_by_flutterwave_in_major_units(self):
        route = respx.get(f"{FLW}/transfers/fee").mock(return_value=httpx.Response(200, json={
            "status": "success", "message": "Transfer fee fetched",
            "data": [{"fee_type": "value", "currency": "NGN", "fee": 26.875}],
        }))

        fee = await FlutterwavePaymentGateway().quote_fee(5_000_000, TransactionCurrency.NGN)

        assert fee == 2_688  # ₦26.875 → 2,687.5 kobo, rounded half up
        params = route.calls.last.request.url.params
        assert (params["amount"], params["currency"], params["type"]) == ("50000.0", "NGN", "account")

    @respx.mock
    async def test_a_percentage_fee_is_applied_to_the_amount(self):
        respx.get(f"{FLW}/transfers/fee").mock(return_value=httpx.Response(200, json={
            "status": "success", "message": "Transfer fee fetched",
            "data": [{"fee_type": "percentage", "currency": "NGN", "fee": 1.4}],
        }))

        assert await FlutterwavePaymentGateway().quote_fee(1_000_000, TransactionCurrency.NGN) == 14_000

    @respx.mock
    async def test_a_transfer_is_sent_in_major_units_under_our_reference(self):
        route = respx.post(f"{FLW}/transfers").mock(return_value=httpx.Response(200, json={
            "status": "success", "message": "Transfer Queued Successfully",
            "data": {"id": 117369760, "account_number": "0690000031", "bank_code": "044", "full_name": "ADA OBI",
                     "currency": "NGN", "amount": 49975.5, "fee": 26.875, "status": "NEW", "reference": REF,
                     "complete_message": "", "requires_approval": 0, "is_approved": 1},
        }))

        sent = await FlutterwavePaymentGateway().send_transfer(_transfer())

        body = json.loads(route.calls.last.request.content)
        assert body == {
            "account_bank": "044", "account_number": "0690000031", "amount": 49975.5, "currency": "NGN",
            "debit_currency": "NGN", "narration": "Veriprops payout", "reference": REF,
            "beneficiary_name": "ADA OBI",
        }
        assert (sent.reference, sent.gateway_transfer_id, sent.status) == (REF, "117369760", GatewayTransferStatus.PENDING)
        assert sent.amount_minor == 4_997_550

    @respx.mock
    async def test_a_transfer_is_found_again_by_our_reference(self):
        route = respx.get(f"{FLW}/transfers").mock(return_value=httpx.Response(200, json={
            "status": "success", "message": "Transfers fetched", "meta": {"page_info": {"total": 1}},
            "data": [{"id": 117369760, "amount": 49975.5, "status": "SUCCESSFUL", "reference": REF,
                      "complete_message": "Transaction was successful"}],
        }))

        found = await FlutterwavePaymentGateway().get_transfer(REF)

        assert route.calls.last.request.url.params["reference"] == REF
        assert (found.status, found.gateway_transfer_id, found.amount_minor) == (
            GatewayTransferStatus.SUCCEEDED, "117369760", 4_997_550,
        )

    @respx.mock
    async def test_a_failed_transfer_carries_the_reason_the_bank_gave(self):
        respx.get(f"{FLW}/transfers").mock(return_value=httpx.Response(200, json={
            "status": "success", "message": "Transfers fetched",
            "data": [{"id": 9, "amount": 100, "status": "FAILED", "reference": REF,
                      "complete_message": "DISBURSE FAILED: Insufficient funds in customer wallet"}],
        }))

        found = await FlutterwavePaymentGateway().get_transfer(REF)

        assert found.status == GatewayTransferStatus.FAILED
        assert found.failure_reason == "DISBURSE FAILED: Insufficient funds in customer wallet"

    @respx.mock
    async def test_a_reference_flutterwave_never_saw_is_no_transfer(self):
        respx.get(f"{FLW}/transfers").mock(return_value=httpx.Response(200, json={
            "status": "success", "message": "Transfers fetched", "data": [],
        }))

        assert await FlutterwavePaymentGateway().get_transfer(REF) is None

    @respx.mock
    async def test_a_refused_transfer_is_a_decline_and_keeps_the_providers_text_out(self):
        respx.post(f"{FLW}/transfers").mock(return_value=httpx.Response(400, json={
            "status": "error", "message": "Payout with this ref already exists", "data": None,
        }))

        with pytest.raises(GatewayDeclined) as exc:
            await FlutterwavePaymentGateway().send_transfer(_transfer())
        # Kept for finance's eyes on the payout, never in the exception a client could see.
        assert "already exists" not in str(exc.value)
        assert exc.value.provider_message == "Payout with this ref already exists"

    @respx.mock
    async def test_a_gateway_that_cannot_be_reached_is_not_a_decline(self):
        respx.post(f"{FLW}/transfers").mock(side_effect=httpx.ConnectTimeout("timed out"))

        with pytest.raises(IntegrationException) as exc:
            await FlutterwavePaymentGateway().send_transfer(_transfer())
        assert not isinstance(exc.value, GatewayDeclined)

    @respx.mock
    async def test_a_server_error_is_not_a_decline_either(self):
        # A 5xx may have come after the transfer was queued: only a lookup can tell.
        respx.post(f"{FLW}/transfers").mock(return_value=httpx.Response(502, json={}))

        with pytest.raises(IntegrationException) as exc:
            await FlutterwavePaymentGateway().send_transfer(_transfer())
        assert not isinstance(exc.value, GatewayDeclined)


# ─── Paystack ────────────────────────────────────────────────────


class TestPaystackTransfers:
    @respx.mock
    async def test_only_active_banks_that_take_transfers_are_listed(self):
        route = respx.get(f"{PSK}/bank").mock(return_value=httpx.Response(200, json={
            "status": True, "message": "Banks retrieved",
            "data": [
                {"name": "Access Bank", "code": "044", "active": True, "supports_transfer": True, "is_deleted": False},
                {"name": "Old Bank", "code": "999", "active": False, "supports_transfer": True, "is_deleted": False},
                {"name": "Collections Only", "code": "998", "active": True, "supports_transfer": False, "is_deleted": False},
                {"name": "Gone Bank", "code": "997", "active": True, "supports_transfer": True, "is_deleted": True},
            ],
            "meta": {"next": None},
        }))

        banks = await PaystackPaymentGateway().list_banks(TransactionCurrency.NGN)

        assert [(b.code, b.name) for b in banks] == [("044", "Access Bank")]
        params = route.calls.last.request.url.params
        assert (params["currency"], params["use_cursor"]) == ("NGN", "true")

    @respx.mock
    async def test_the_bank_list_is_followed_across_pages(self):
        route = respx.get(f"{PSK}/bank").mock(side_effect=[
            httpx.Response(200, json={"status": True, "message": "ok", "meta": {"next": "cur-2"},
                                      "data": [{"name": "A", "code": "001", "active": True, "supports_transfer": True}]}),
            httpx.Response(200, json={"status": True, "message": "ok", "meta": {"next": None},
                                      "data": [{"name": "B", "code": "002", "active": True, "supports_transfer": True}]}),
        ])

        banks = await PaystackPaymentGateway().list_banks(TransactionCurrency.NGN)

        assert [b.code for b in banks] == ["001", "002"]
        assert route.calls.last.request.url.params["next"] == "cur-2"

    @respx.mock
    async def test_an_account_resolves_to_the_name_the_bank_holds(self):
        route = respx.get(f"{PSK}/bank/resolve").mock(return_value=httpx.Response(200, json={
            "status": True, "message": "Account number resolved",
            "data": {"account_number": "0001234567", "account_name": "ADA OBI", "bank_id": 9},
        }))

        account = await PaystackPaymentGateway().resolve_account("058", "0001234567")

        params = route.calls.last.request.url.params
        assert (params["account_number"], params["bank_code"]) == ("0001234567", "058")
        assert account.account_name == "ADA OBI"

    @respx.mock
    async def test_an_account_paystack_cannot_resolve_resolves_to_nothing(self):
        respx.get(f"{PSK}/bank/resolve").mock(return_value=httpx.Response(422, json={
            "status": False, "message": "Could not resolve account name. Check parameters or try again.",
        }))

        assert await PaystackPaymentGateway().resolve_account("058", "0000000000") is None

    @pytest.mark.parametrize("amount_minor, fee_minor", [
        (500_000, 1_000),       # up to ₦5,000: ₦10
        (500_001, 2_500),       # ₦5,000.01 – ₦50,000: ₦25
        (5_000_000, 2_500),
        (5_000_001, 5_000),     # above ₦50,000: ₦50
    ])
    async def test_the_fee_comes_from_paystacks_published_table(self, amount_minor, fee_minor):
        # Paystack has no fee endpoint; its NGN transfer pricing is a three-band table.
        assert await PaystackPaymentGateway().quote_fee(amount_minor, TransactionCurrency.NGN) == fee_minor

    async def test_a_currency_without_a_published_fee_is_refused(self):
        with pytest.raises(IntegrationException):
            await PaystackPaymentGateway().quote_fee(10_000, TransactionCurrency.USD)

    @respx.mock
    async def test_a_transfer_goes_to_a_recipient_created_from_the_resolved_account(self):
        recipient = respx.post(f"{PSK}/transferrecipient").mock(return_value=httpx.Response(201, json={
            "status": True, "message": "Transfer recipient created successfully",
            "data": {"recipient_code": "RCP_abc", "name": "ADA OBI", "active": True},
        }))
        transfer = respx.post(f"{PSK}/transfer").mock(return_value=httpx.Response(200, json={
            "status": True, "message": "Transfer has been queued",
            "data": {"id": 476948, "reference": REF, "amount": 4_997_550, "currency": "NGN",
                     "status": "pending", "transfer_code": "TRF_1ptvuv321ahaa7q"},
        }))

        sent = await PaystackPaymentGateway().send_transfer(_transfer())

        assert json.loads(recipient.calls.last.request.content) == {
            "type": "nuban", "name": "ADA OBI", "account_number": "0690000031", "bank_code": "044", "currency": "NGN",
        }
        assert json.loads(transfer.calls.last.request.content) == {
            "source": "balance", "amount": 4_997_550, "recipient": "RCP_abc", "reference": REF,
            "reason": "Veriprops payout", "currency": "NGN",
        }
        assert (sent.gateway_transfer_id, sent.status) == ("TRF_1ptvuv321ahaa7q", GatewayTransferStatus.PENDING)

    @pytest.mark.parametrize("status, expected", [
        ("success", GatewayTransferStatus.SUCCEEDED),
        ("failed", GatewayTransferStatus.FAILED),
        ("reversed", GatewayTransferStatus.FAILED),
        ("abandoned", GatewayTransferStatus.FAILED),
        ("rejected", GatewayTransferStatus.FAILED),
        ("blocked", GatewayTransferStatus.FAILED),
        ("pending", GatewayTransferStatus.PENDING),
        ("received", GatewayTransferStatus.PENDING),
        # Transfer OTP is on for the account: nothing moves until someone finalises it.
        ("otp", GatewayTransferStatus.PENDING),
        ("some-new-status", GatewayTransferStatus.PENDING),
    ])
    @respx.mock
    async def test_a_transfer_is_verified_by_our_reference(self, status, expected):
        route = respx.get(f"{PSK}/transfer/verify/{REF}").mock(return_value=httpx.Response(200, json={
            "status": True, "message": "Transfer retrieved",
            "data": {"id": 476948, "reference": REF, "amount": 4_997_550, "status": status,
                     "transfer_code": "TRF_1ptvuv321ahaa7q", "failures": None},
        }))

        found = await PaystackPaymentGateway().get_transfer(REF)

        assert route.called
        assert (found.status, found.gateway_transfer_id, found.amount_minor) == (
            expected, "TRF_1ptvuv321ahaa7q", 4_997_550,
        )

    @respx.mock
    async def test_a_reference_paystack_never_saw_is_no_transfer(self):
        respx.get(f"{PSK}/transfer/verify/{REF}").mock(return_value=httpx.Response(404, json={
            "status": False, "message": "Transfer not found",
        }))

        assert await PaystackPaymentGateway().get_transfer(REF) is None

    @respx.mock
    async def test_a_refused_recipient_is_a_decline(self):
        respx.post(f"{PSK}/transferrecipient").mock(return_value=httpx.Response(400, json={
            "status": False, "message": "Account number is invalid",
        }))

        with pytest.raises(GatewayDeclined):
            await PaystackPaymentGateway().send_transfer(_transfer())

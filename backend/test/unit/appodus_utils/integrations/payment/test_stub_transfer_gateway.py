"""The stub transfer gateway that CI, e2e and local runs pay agents through (PAYMENT_STUB_MODE).

It answers like a live gateway, so the payout flow above it is the one production runs:
a bank list, a bank-held name, a fee from a real tariff, and a transfer that settles at once.
One documented account number declines, so the failed-transfer path is drivable end to end.
"""
import pytest

from main.appodus_utils.db.types.money import TransactionCurrency
from main.appodus_utils.integrations.payment.gateway.models import GatewayTransferStatus, TransferRequest
from main.appodus_utils.integrations.payment.gateway.stub import (
    STUB_DECLINING_ACCOUNT_NUMBER,
    STUB_UNKNOWN_ACCOUNT_NUMBER,
    StubTransferGateway,
)


def _transfer(reference="vp-po-0123456789abcdef0123456789abcdef-1", account_number="0123456789"):
    return TransferRequest(
        reference=reference, amount_minor=100_000, currency=TransactionCurrency.NGN,
        bank_code="058", account_number=account_number, account_name="TEST ACCOUNT 6789",
        narration="Veriprops payout",
    )


@pytest.fixture
def gateway():
    return StubTransferGateway()


class TestStubTransferGateway:
    async def test_it_lists_banks(self, gateway):
        banks = await gateway.list_banks(TransactionCurrency.NGN)
        assert banks and all(b.code and b.name for b in banks)
        assert len({b.code for b in banks}) == len(banks)

    async def test_an_account_resolves_to_a_bank_held_name(self, gateway):
        account = await gateway.resolve_account("058", "0123456789")
        assert account.account_name == "TEST ACCOUNT 6789"

    async def test_an_unlisted_bank_or_the_unknown_number_resolves_to_nothing(self, gateway):
        assert await gateway.resolve_account("not-a-bank", "0123456789") is None
        assert await gateway.resolve_account("058", STUB_UNKNOWN_ACCOUNT_NUMBER) is None

    async def test_the_fee_follows_a_real_tariff(self, gateway):
        assert await gateway.quote_fee(500_000, TransactionCurrency.NGN) == 1_000

    async def test_a_transfer_settles_at_once_and_can_be_found_again(self, gateway):
        sent = await gateway.send_transfer(_transfer())

        assert sent.status == GatewayTransferStatus.SUCCEEDED
        found = await gateway.get_transfer(sent.reference)
        assert (found.status, found.gateway_transfer_id) == (GatewayTransferStatus.SUCCEEDED, sent.gateway_transfer_id)

    async def test_the_declining_account_fails_with_a_reason(self, gateway):
        sent = await gateway.send_transfer(_transfer(account_number=STUB_DECLINING_ACCOUNT_NUMBER))

        assert sent.status == GatewayTransferStatus.FAILED
        assert sent.failure_reason

    async def test_a_reference_it_never_sent_is_no_transfer(self, gateway):
        assert await gateway.get_transfer("vp-po-ffffffffffffffffffffffffffffffff-1") is None

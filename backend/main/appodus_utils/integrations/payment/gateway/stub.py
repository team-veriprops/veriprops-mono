"""The transfer gateway CI, e2e and local runs pay agents through (PAYMENT_STUB_MODE).

It answers like a live gateway so the payout flow above it is the one production runs: a
bank list, a bank-held account name, a fee from a real tariff (Paystack's), and a transfer
that settles the moment it is sent. It never leaves the process.

Two documented account numbers drive the unhappy paths: one no bank knows, and one whose
transfers the bank declines.
"""
from __future__ import annotations

import secrets
from typing import Dict, List, Optional

from main.appodus_utils.db.types.money import TransactionCurrency
from main.appodus_utils.integrations.exception.exceptions import IntegrationException
from main.appodus_utils.integrations.payment.gateway.interface import ITransferGateway
from main.appodus_utils.integrations.payment.gateway.models import (
    GatewayAccount,
    GatewayBank,
    GatewayTransfer,
    GatewayTransferStatus,
    TransferRequest,
)
from main.appodus_utils.integrations.payment.gateway.paystack.payment import paystack_ngn_transfer_fee

# Resolves to nothing, as an account number no bank holds would.
STUB_UNKNOWN_ACCOUNT_NUMBER = "0000000000"
# Resolves, but every transfer to it fails at the bank.
STUB_DECLINING_ACCOUNT_NUMBER = "0000009999"
STUB_DECLINE_REASON = "Stub: the beneficiary bank rejected the transfer"

# A handful of real Nigerian banks and their NIP codes, so screens and tests read naturally.
STUB_BANKS: List[GatewayBank] = [
    GatewayBank(code="044", name="Access Bank"),
    GatewayBank(code="011", name="First Bank of Nigeria"),
    GatewayBank(code="058", name="Guaranty Trust Bank"),
    GatewayBank(code="999992", name="OPay"),
    GatewayBank(code="033", name="United Bank For Africa"),
    GatewayBank(code="057", name="Zenith Bank"),
]

# Every transfer this process sent, by our reference.
_SENT: Dict[str, GatewayTransfer] = {}


class StubTransferGateway(ITransferGateway):
    async def list_banks(self, currency: TransactionCurrency) -> List[GatewayBank]:
        return list(STUB_BANKS)

    async def resolve_account(self, bank_code: str, account_number: str) -> Optional[GatewayAccount]:
        if account_number == STUB_UNKNOWN_ACCOUNT_NUMBER or bank_code not in {b.code for b in STUB_BANKS}:
            return None
        return GatewayAccount(
            bank_code=bank_code, account_number=account_number,
            account_name=f"TEST ACCOUNT {account_number[-4:]}",
        )

    async def quote_fee(self, amount_minor: int, currency: TransactionCurrency) -> int:
        if currency != TransactionCurrency.NGN:
            raise IntegrationException(f"Could not quote the transfer fee: no {currency.value} tariff is known.")
        return paystack_ngn_transfer_fee(amount_minor)

    async def send_transfer(self, request: TransferRequest) -> GatewayTransfer:
        declined = request.account_number == STUB_DECLINING_ACCOUNT_NUMBER
        sent = GatewayTransfer(
            reference=request.reference,
            gateway_transfer_id=f"STUB_TRF_{secrets.token_hex(6)}",
            status=GatewayTransferStatus.FAILED if declined else GatewayTransferStatus.SUCCEEDED,
            amount_minor=request.amount_minor,
            failure_reason=STUB_DECLINE_REASON if declined else None,
        )
        _SENT[request.reference] = sent
        return sent

    async def get_transfer(self, reference: str) -> Optional[GatewayTransfer]:
        return _SENT.get(reference)

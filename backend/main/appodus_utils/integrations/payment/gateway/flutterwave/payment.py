from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger

from kink import di, inject

from main.app.config.settings import IntegratedPlatform, settings
from decimal import ROUND_HALF_UP, Decimal
from typing import List, Optional

from main.appodus_utils.db.types.money import TransactionCurrency
from main.appodus_utils.integrations.exception.exceptions import IntegrationException
from main.appodus_utils.integrations.payment.gateway.http import GatewayHttp, GatewayNotFound
from main.appodus_utils.integrations.payment.gateway.interface import IPaymentGateway, ITransferGateway
from main.appodus_utils.integrations.payment.gateway.models import (
    GatewayAccount,
    GatewayBank,
    GatewayCharge,
    GatewayChargeStatus,
    GatewayTransfer,
    GatewayTransferStatus,
    HostedCheckoutRequest,
    TransferRequest,
    to_major_units,
    to_minor_units,
)

logger: Logger = di["logger"]


# Flutterwave v3 charge statuses; anything else (pending, or a status added later) is PENDING.
_FLW_STATUS = {"successful": GatewayChargeStatus.SUCCEEDED, "failed": GatewayChargeStatus.FAILED}
# Flutterwave v3 transfer statuses (NEW, PENDING, SUCCESSFUL, FAILED); NEW/PENDING are in flight.
_FLW_TRANSFER_STATUS = {"SUCCESSFUL": GatewayTransferStatus.SUCCEEDED, "FAILED": GatewayTransferStatus.FAILED}
# The country Flutterwave lists a currency's banks under.
_FLW_TRANSFER_COUNTRY = {TransactionCurrency.NGN: "NG"}


def _flw_ok(body: dict) -> bool:
    return body.get("status") == "success"


def _flw_no_transaction(status_code: int, body: dict) -> bool:
    """Flutterwave answers a reference it never charged with 400/404 "No transaction was found"."""
    return status_code in (400, 404) and "no transaction" in str(body.get("message", "")).lower()


@inject
class FlutterwavePaymentGateway(IPaymentGateway, ITransferGateway):
    """Flutterwave v3. Amounts are major units on the wire (1500.5 = ₦1,500.50)."""

    def __init__(self):
        self._http = GatewayHttp("Flutterwave", settings.FLUTTERWAVE_BASE_URL, settings.FLUTTERWAVE_SECRET_KEY, _flw_ok)

    @property
    def platform(self) -> IntegratedPlatform:
        return IntegratedPlatform.FLUTTERWAVE

    async def create_hosted_checkout(self, request: HostedCheckoutRequest) -> str:
        """POST /payments → ``data.link``, the Flutterwave Standard hosted page."""
        data = await self._http.request("POST", "/payments", action="open the checkout", json={
            "tx_ref": request.reference,
            "amount": to_major_units(request.amount_minor),
            "currency": request.currency.value,
            "redirect_url": request.redirect_url,
            "customer": {
                "email": request.customer_email,
                "phonenumber": request.customer_phone,
                "name": request.customer_name,
            },
            "customizations": {"title": request.title, "description": request.description},
        })
        return data["link"]

    async def get_charge(self, reference: str) -> Optional[GatewayCharge]:
        """GET /transactions/verify_by_reference?tx_ref=… (the id-keyed /verify needs Flutterwave's id)."""
        try:
            data = await self._http.request(
                "GET", "/transactions/verify_by_reference", action="check the payment",
                params={"tx_ref": reference}, not_found_when=_flw_no_transaction,
            )
        except GatewayNotFound:
            return None
        return GatewayCharge(
            reference=data["tx_ref"],
            gateway_transaction_id=str(data["id"]),
            gateway_reference=str(data.get("flw_ref") or data["id"]),
            status=_FLW_STATUS.get(str(data.get("status", "")).lower(), GatewayChargeStatus.PENDING),
            # `amount` is what was asked for; `charged_amount` adds any fee the customer bore.
            amount_minor=to_minor_units(data["amount"]),
            currency=TransactionCurrency(data["currency"]),
        )

    async def refund_charge(self, reference: str, amount_minor: int, reason: Optional[str]) -> None:
        """POST /transactions/{id}/refund — Flutterwave refunds by its own transaction id."""
        charge = await self.get_charge(reference)
        if charge is None:
            raise IntegrationException("Could not refund the payment: the gateway has no record of it.")
        await self._http.request(
            "POST", f"/transactions/{charge.gateway_transaction_id}/refund", action="refund the payment",
            json={"amount": to_major_units(amount_minor), "comments": reason},
        )

    # ── Transfers ────────────────────────────────────────────────

    async def list_banks(self, currency: TransactionCurrency) -> List[GatewayBank]:
        """GET /banks/{country}. Flutterwave lists banks by country; NGN is Nigeria."""
        country = _FLW_TRANSFER_COUNTRY.get(currency)
        if country is None:
            raise IntegrationException(f"Could not list banks: {currency.value} transfers are not supported.")
        data = await self._http.request("GET", f"/banks/{country}", action="list the banks")
        return [GatewayBank(code=str(b["code"]), name=b["name"]) for b in data or []]

    async def resolve_account(self, bank_code: str, account_number: str) -> Optional[GatewayAccount]:
        """POST /accounts/resolve → the name the bank holds for the account."""
        try:
            data = await self._http.request(
                "POST", "/accounts/resolve", action="check the bank account",
                json={"account_number": account_number, "account_bank": bank_code},
                not_found_when=_flw_account_unknown,
            )
        except GatewayNotFound:
            return None
        return GatewayAccount(bank_code=bank_code, account_number=account_number, account_name=data["account_name"])

    async def quote_fee(self, amount_minor: int, currency: TransactionCurrency) -> int:
        """GET /transfers/fee — Flutterwave quotes each currency's fee as a value or a percentage."""
        data = await self._http.request(
            "GET", "/transfers/fee", action="quote the transfer fee",
            params={"amount": to_major_units(amount_minor), "currency": currency.value, "type": "account"},
        )
        quote = next((q for q in data or [] if q.get("currency") == currency.value), None)
        if quote is None:
            raise IntegrationException("Could not quote the transfer fee: the gateway returned no fee for the currency.")
        if quote.get("fee_type") == "percentage":
            return int((Decimal(amount_minor) * Decimal(str(quote["fee"])) / 100).to_integral_value(rounding=ROUND_HALF_UP))
        return to_minor_units(quote["fee"])

    async def send_transfer(self, request: TransferRequest) -> GatewayTransfer:
        """POST /transfers, in major units, straight to the account (no beneficiary record)."""
        data = await self._http.request("POST", "/transfers", action="send the transfer", json={
            "account_bank": request.bank_code,
            "account_number": request.account_number,
            "amount": to_major_units(request.amount_minor),
            "currency": request.currency.value,
            "debit_currency": request.currency.value,
            "narration": request.narration,
            "reference": request.reference,
            "beneficiary_name": request.account_name,
        })
        return _flw_transfer(data)

    async def get_transfer(self, reference: str) -> Optional[GatewayTransfer]:
        """GET /transfers?reference=… (the id-keyed GET /transfers/{id} needs Flutterwave's id)."""
        data = await self._http.request(
            "GET", "/transfers", action="check the transfer", params={"reference": reference},
        )
        match = next((t for t in data or [] if t.get("reference") == reference), None)
        return None if match is None else _flw_transfer(match)


def _flw_account_unknown(status_code: int, body: dict) -> bool:
    """Flutterwave answers an account it cannot resolve with a 4xx "invalid account"."""
    return status_code in (400, 404, 422)


def _flw_transfer(data: dict) -> GatewayTransfer:
    status = _FLW_TRANSFER_STATUS.get(str(data.get("status", "")).upper(), GatewayTransferStatus.PENDING)
    return GatewayTransfer(
        reference=data["reference"],
        gateway_transfer_id=str(data["id"]),
        status=status,
        amount_minor=to_minor_units(data["amount"]),
        failure_reason=(data.get("complete_message") or None) if status == GatewayTransferStatus.FAILED else None,
    )

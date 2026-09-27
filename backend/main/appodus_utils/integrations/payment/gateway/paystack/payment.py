from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from kink import di, inject

from main.app.config.settings import IntegratedPlatform, settings
from main.appodus_utils.integrations.exception.exceptions import IntegrationException

if TYPE_CHECKING:
    from loguru import Logger

from main.appodus_utils.db.types.money import TransactionCurrency
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
)
from main.appodus_utils.integrations.payment.gateway.paystack.mapper import PaystackMapper

logger: Logger = di["logger"]


# Paystack transaction statuses. `reversed` is money that came back out, so it never settles a
# payment; `abandoned`/`ongoing`/`pending` (and anything new) have not settled either way.
_PSK_STATUS = {
    "success": GatewayChargeStatus.SUCCEEDED,
    "failed": GatewayChargeStatus.FAILED,
    "reversed": GatewayChargeStatus.FAILED,
}
# Paystack transfer statuses. Anything that ends with the money back in our balance is FAILED;
# `pending`/`received`/`otp` (and anything new) are still in flight.
_PSK_TRANSFER_STATUS = {
    "success": GatewayTransferStatus.SUCCEEDED,
    "failed": GatewayTransferStatus.FAILED,
    "reversed": GatewayTransferStatus.FAILED,
    "abandoned": GatewayTransferStatus.FAILED,
    "rejected": GatewayTransferStatus.FAILED,
    "blocked": GatewayTransferStatus.FAILED,
}


def _psk_ok(body: dict) -> bool:
    return body.get("status") is True


def _psk_not_found(status_code: int, body: dict) -> bool:
    return status_code == 404 or (status_code == 400 and "not found" in str(body.get("message", "")).lower())


@inject
class PaystackPaymentGateway(IPaymentGateway, ITransferGateway):
    """Paystack. Amounts are kobo (or the currency's minor unit) on the wire."""

    def __init__(self):
        self._http = GatewayHttp("Paystack", settings.PAYSTACK_BASE_URL, settings.PAYSTACK_SECRET_KEY, _psk_ok)

    @property
    def platform(self) -> IntegratedPlatform:
        return IntegratedPlatform.PAYSTACK

    async def create_hosted_checkout(self, request: HostedCheckoutRequest) -> str:
        """POST /transaction/initialize → ``data.authorization_url``."""
        data = await self._http.request(
            "POST", "/transaction/initialize", action="open the checkout",
            json=PaystackMapper.to_init_payment_dto(request).model_dump(mode="json", exclude_none=True),
        )
        return data["authorization_url"]

    async def get_charge(self, reference: str) -> Optional[GatewayCharge]:
        """GET /transaction/verify/{reference}."""
        try:
            data = await self._http.request(
                "GET", f"/transaction/verify/{reference}", action="check the payment",
                not_found_when=_psk_not_found,
            )
        except GatewayNotFound:
            return None
        transaction_id = str(data["id"])
        return GatewayCharge(
            reference=data["reference"],
            gateway_transaction_id=transaction_id,
            # Paystack's own handle for a transaction is its id; disputes cite it too.
            gateway_reference=transaction_id,
            status=_PSK_STATUS.get(str(data.get("status", "")).lower(), GatewayChargeStatus.PENDING),
            amount_minor=int(data["amount"]),
            currency=TransactionCurrency(data["currency"]),
        )

    async def refund_charge(self, reference: str, amount_minor: int, reason: Optional[str]) -> None:
        """POST /refund, naming the transaction by our reference."""
        body = {"transaction": reference, "amount": amount_minor}
        if reason:
            body["merchant_note"] = reason
        await self._http.request("POST", "/refund", action="refund the payment", json=body)

    # ── Transfers ────────────────────────────────────────────────

    async def list_banks(self, currency: TransactionCurrency) -> List[GatewayBank]:
        """GET /bank?currency=…, following the cursor; only live banks that take transfers."""
        banks: List[GatewayBank] = []
        cursor: Optional[str] = None
        for _ in range(_BANK_LIST_MAX_PAGES):
            params: Dict[str, object] = {"currency": currency.value, "use_cursor": "true", "perPage": 100}
            if cursor:
                params["next"] = cursor
            body = await self._http.request("GET", "/bank", action="list the banks", params=params, envelope=True)
            banks.extend(
                GatewayBank(code=str(b["code"]), name=b["name"])
                for b in body.get("data") or []
                if b.get("active", True) and b.get("supports_transfer", True) and not b.get("is_deleted")
            )
            cursor = (body.get("meta") or {}).get("next")
            if not cursor:
                break
        return banks

    async def resolve_account(self, bank_code: str, account_number: str) -> Optional[GatewayAccount]:
        """GET /bank/resolve → the name the bank holds for the account."""
        try:
            data = await self._http.request(
                "GET", "/bank/resolve", action="check the bank account",
                params={"account_number": account_number, "bank_code": bank_code},
                not_found_when=_psk_account_unknown,
            )
        except GatewayNotFound:
            return None
        return GatewayAccount(bank_code=bank_code, account_number=account_number, account_name=data["account_name"])

    async def quote_fee(self, amount_minor: int, currency: TransactionCurrency) -> int:
        """Paystack publishes its transfer pricing but has no endpoint for it: read the table."""
        bands = _PSK_TRANSFER_FEE_BANDS.get(currency)
        if bands is None:
            raise IntegrationException(f"Could not quote the transfer fee: no {currency.value} tariff is known.")
        return paystack_band_fee(amount_minor, bands)

    async def send_transfer(self, request: TransferRequest) -> GatewayTransfer:
        """POST /transferrecipient for the resolved account, then POST /transfer from the balance.

        Paystack returns the existing recipient for an account it already holds, so creating
        one per transfer is safe."""
        recipient = await self._http.request("POST", "/transferrecipient", action="register the bank account", json={
            "type": "nuban",
            "name": request.account_name,
            "account_number": request.account_number,
            "bank_code": request.bank_code,
            "currency": request.currency.value,
        })
        data = await self._http.request("POST", "/transfer", action="send the transfer", json={
            "source": "balance",
            "amount": request.amount_minor,
            "recipient": recipient["recipient_code"],
            "reference": request.reference,
            "reason": request.narration,
            "currency": request.currency.value,
        })
        return _psk_transfer(data, request.reference)

    async def get_transfer(self, reference: str) -> Optional[GatewayTransfer]:
        """GET /transfer/verify/{reference}."""
        try:
            data = await self._http.request(
                "GET", f"/transfer/verify/{reference}", action="check the transfer",
                not_found_when=_psk_not_found,
            )
        except GatewayNotFound:
            return None
        return _psk_transfer(data, reference)


# Paystack's NGN transfer pricing, as (upper bound inclusive, fee) in kobo; the last band is open.
# ₦10 up to ₦5,000; ₦25 up to ₦50,000; ₦50 above.
_PSK_TRANSFER_FEE_BANDS: Dict[TransactionCurrency, List[Tuple[Optional[int], int]]] = {
    TransactionCurrency.NGN: [(500_000, 1_000), (5_000_000, 2_500), (None, 5_000)],
}
# The bank list is a few hundred rows; a cursor that never ends is a gateway fault.
_BANK_LIST_MAX_PAGES = 20


def paystack_band_fee(amount_minor: int, bands: List[Tuple[Optional[int], int]]) -> int:
    """The fee of the first band whose upper bound covers *amount_minor*."""
    for ceiling, fee in bands:
        if ceiling is None or amount_minor <= ceiling:
            return fee
    raise ValueError("A fee table must end with an open band.")


def paystack_ngn_transfer_fee(amount_minor: int) -> int:
    """Paystack's published fee for an NGN transfer of *amount_minor*."""
    return paystack_band_fee(amount_minor, _PSK_TRANSFER_FEE_BANDS[TransactionCurrency.NGN])


def _psk_account_unknown(status_code: int, body: dict) -> bool:
    """Paystack answers an account it cannot resolve with a 4xx ("Could not resolve account name")."""
    return status_code in (400, 404, 422)


def _psk_transfer(data: dict, reference: str) -> GatewayTransfer:
    raw_status = str(data.get("status", "")).lower()
    status = _PSK_TRANSFER_STATUS.get(raw_status, GatewayTransferStatus.PENDING)
    if raw_status == "otp":
        logger.warning("Paystack is holding a transfer for OTP; disable transfer OTP on the account")
    failures = data.get("failures")
    return GatewayTransfer(
        reference=data.get("reference") or reference,
        # The transfer code is Paystack's handle for a transfer (fetch, finalize, disputes).
        gateway_transfer_id=str(data.get("transfer_code") or data["id"]),
        status=status,
        amount_minor=int(data["amount"]),
        failure_reason=(str(failures) if failures else None) if status == GatewayTransferStatus.FAILED else None,
    )

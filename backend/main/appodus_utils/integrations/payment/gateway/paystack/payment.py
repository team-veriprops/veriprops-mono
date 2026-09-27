from httpx import AsyncClient
from kink import di, inject

from main.app.config.settings import IntegratedPlatform, settings
from main.appodus_utils.exception.exceptions import NotImplementedException
from typing import Optional

from main.appodus_utils.db.types.money import TransactionCurrency
from main.appodus_utils.integrations.payment.gateway.http import GatewayHttp, GatewayNotFound
from main.appodus_utils.integrations.payment.gateway.interface import IPaymentGateway
from main.appodus_utils.integrations.payment.gateway.models import (
    BankTransferRequest,
    BankTransferResponse,
    CountryBanksResponse,
    GatewayCharge,
    GatewayChargeStatus,
    GenericPaymentGatewayResponse,
    HostedCheckoutRequest,
    TransferFeeRequest,
    TransferFeeResponse,
)
from main.appodus_utils.integrations.payment.gateway.paystack.mapper import PaystackMapper
from main.appodus_utils.integrations.payment.gateway.paystack.models import (
    CreateRecipientRequest,
    CreateRecipientResponse,
)

httpx_client: AsyncClient = di[AsyncClient]


# Paystack transaction statuses. `reversed` is money that came back out, so it never settles a
# payment; `abandoned`/`ongoing`/`pending` (and anything new) have not settled either way.
_PSK_STATUS = {
    "success": GatewayChargeStatus.SUCCEEDED,
    "failed": GatewayChargeStatus.FAILED,
    "reversed": GatewayChargeStatus.FAILED,
}


def _psk_ok(body: dict) -> bool:
    return body.get("status") is True


def _psk_not_found(status_code: int, body: dict) -> bool:
    return status_code == 404 or (status_code == 400 and "not found" in str(body.get("message", "")).lower())


@inject
class PaystackPaymentGateway(IPaymentGateway):
    """Paystack. Amounts are kobo (or the currency's minor unit) on the wire."""

    def __init__(self):
        self.base_url = settings.PAYSTACK_BASE_URL
        self.headers = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}", "Content-Type": "application/json",
                        "Accept": "application/json"}
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

    async def _create_recipient(self, payload: CreateRecipientRequest) -> CreateRecipientResponse:
        """
        Creates a transfer recipient on Paystack.

        ✅ Required Fields:
        - `type`: Recipient type (usually "nuban")
        - `name`: Full name of the recipient
        - `account_number`: Recipient’s bank account number
        - `bank_code`: Code of the bank (e.g. "044" for GTBank)
        - `currency`: e.g. "NGN"

        🔁 Sample Request:
        {
            "type": "nuban",
            "name": "John Doe",
            "account_number": "0690000031",
            "bank_code": "044",
            "currency": "NGN"
        }

        ✅ Sample Response:
        {
            "status": true,
            "message": "Transfer recipient created successfully",
            "data": {
                "recipient_code": "RCP_1A234B567C",
                "name": "John Doe",
                "account_number": "0690000031",
                "bank_code": "044",
                "currency": "NGN",
                ...
            }
        }

        Returns:
            CreateRecipientResponse: Contains recipient code and related details.
        """
        url = f"{self.base_url}/transferrecipient"
        response = await httpx_client.post(url, headers=self.headers, json=payload.model_dump())
        response.raise_for_status()
        return CreateRecipientResponse(**response.json())

    async def initialize_bank_transfer(self, payload: BankTransferRequest) -> BankTransferResponse:
        """
        Initiates a single bank transfer using `/transfer`.

        ✅ Required Fields:
        - `recipient` (str): Recipient code (must be created first)
        - `amount` (int): Amount in kobo
        - `reason` (str): Purpose of transfer

        ✅ Sample Response:
        {
            "status": true,
            "data": {
                "transfer_code": "TRF_vsyqdmlzble3uii",
                "status": "NEW",
                ...
            }
        }

        Returns:
            BankTransferResponse
        """
        # Create Recipient
        if not payload.recipient_code:
            create_recipient_dto = CreateRecipientRequest(type="nuban", name=payload.fullname,
                account_number=payload.account_number, bank_code=payload.account_bank, currency=payload.currency)
            created_recipient = await self._create_recipient(create_recipient_dto)

            payload.recipient_code = created_recipient.data.recipient_code

        payload_dict = payload.model_dump()
        payload_dict["amount"] = int(payload.amount * 100)  # in kobo
        payload_dict["source"] = "balance"
        payload_dict["reason"] = payload.narration
        payload_dict["recipient"] = payload.recipient_code
        response = await httpx_client.post(f"{self.base_url}/transfer", headers=self.headers, json=payload_dict)
        response.raise_for_status()
        return BankTransferResponse(**response.json())

    async def retry_failed_bank_transfer(self, transfer_ref_id: str) -> GenericPaymentGatewayResponse:
        """
        Finalizes a previously failed or pending transfer using `/transfer/finalize_transfer`.

        ✅ Required:
        - `transfer_code` (str): Code of the failed transfer

        ✅ Sample Response:
        {
            "status": true,
            "message": "Transfer finalized successfully"
        }

        Returns:
            RetryTransferResponse
        """
        raise NotImplementedException("Feature not natively available in Paystack client.")

    async def get_transfer_fee(self, payload: TransferFeeRequest) -> TransferFeeResponse:
        """
        Retrieves the estimated fee for a transfer using `/transfer/fee`.

        ✅ Required:
        - `amount` (int): Amount in kobo

        ✅ Sample Response:
        {
            "status": true,
            "data": {
                "fee": 10500,
                "currency": "NGN",
                "amount": 500000
            }
        }

        Returns:
            TransferFeeResponse
        """
        # TODO(gap): Paystack exposes no transfer-fee endpoint, so the figure has to be
        # computed locally from their published transfer-cost table — unwired while payouts
        # run against the stub disburser — PRD "Known Gaps & Roadmap".
        raise NotImplementedException("Feature not natively available in Paystack client.")

    async def get_all_country_banks(self, country_code: str) -> CountryBanksResponse:
        """
        Retrieves a list of banks by country using `/bank?country=XX`.

        ✅ Required:
        - `country_code` (str): ISO country code (e.g., "NG")

        ✅ Sample Response:
        {
            "status": true,
            "data": [
                {"name": "GTBank", "code": "058"},
                {"name": "Access Bank", "code": "044"},
                ...
            ]
        }

        Returns:
            CountryBanksResponse
        """
        response = await httpx_client.get(f"{self.base_url}/bank", headers=self.headers,
                                          params={"country": country_code})
        response.raise_for_status()
        return CountryBanksResponse(**response.json())

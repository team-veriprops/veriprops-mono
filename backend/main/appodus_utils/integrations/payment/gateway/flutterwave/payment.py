from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger

from httpx import AsyncClient
from kink import di, inject

from main.app.config.settings import IntegratedPlatform, settings
from typing import Optional

from main.appodus_utils.db.types.money import TransactionCurrency
from main.appodus_utils.integrations.exception.exceptions import IntegrationException
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
    to_major_units,
    to_minor_units,
)
from main.appodus_utils.integrations.payment.gateway.paystack.models import CreateRecipientRequest, CreateRecipientResponse

httpx_client: AsyncClient = di[AsyncClient]
logger: Logger = di["logger"]


# Flutterwave v3 charge statuses; anything else (pending, or a status added later) is PENDING.
_FLW_STATUS = {"successful": GatewayChargeStatus.SUCCEEDED, "failed": GatewayChargeStatus.FAILED}


def _flw_ok(body: dict) -> bool:
    return body.get("status") == "success"


def _flw_no_transaction(status_code: int, body: dict) -> bool:
    """Flutterwave answers a reference it never charged with 400/404 "No transaction was found"."""
    return status_code in (400, 404) and "no transaction" in str(body.get("message", "")).lower()


@inject
class FlutterwavePaymentGateway(IPaymentGateway):
    """Flutterwave v3. Amounts are major units on the wire (1500.5 = ₦1,500.50)."""

    def __init__(self):
        self.base_url = settings.FLUTTERWAVE_BASE_URL
        self.headers = {"Authorization": f"Bearer {settings.FLUTTERWAVE_SECRET_KEY}", "Content-Type": "application/json",
                        "Accept": "application/json"}
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

    async def _create_recipient(self, payload: CreateRecipientRequest) -> CreateRecipientResponse:
        """
        Creates a transfer beneficiary on Flutterwave via the /v3/beneficiaries endpoint.

        ✅ Required Fields:
        - `account_number` (str): Recipient’s bank account number
        - `account_bank` (str): Bank code of the recipient’s bank (e.g. "044" for GTBank)
        - `currency` (str): Currency to be used, e.g. "NGN"
        - `name` (str): Full name of the beneficiary (mapped to `beneficiary_name` in Flutterwave)

        🔁 Sample Request Payload:
        {
            "account_number": "0690000031",
            "account_bank": "044",
            "currency": "NGN",
            "beneficiary_name": "John Doe"
        }

        ✅ Sample Successful Response:
        {
            "status": "success",
            "message": "Beneficiary created",
            "data": {
                "id": 129829,
                "account_number": "0690000031",
                "account_bank": "044",
                "beneficiary_name": "John Doe",
                "date_created": "2023-06-01T12:00:00.000Z",
                "currency": "NGN"
            }
        }

        ⚠️ Notes:
        - Flutterwave does not use `type` or `recipient_code` like Paystack.
        - Instead, the response includes an internal `id` used to reference the beneficiary.

        Returns:
            CreateRecipientResponse: Pydantic model with `status`, `message`, and `data` fields.
        """
        payload_dict = payload.model_dump()
        payload_dict["beneficiary_name"] = payload.name

        url = f"{self.base_url}/beneficiaries"
        response = await httpx_client.post(url, headers=self.headers, json=payload_dict)
        response.raise_for_status()
        return CreateRecipientResponse(**response.json())

    async def initialize_bank_transfer(self, payload: BankTransferRequest) -> BankTransferResponse:
        """
        Initiates a single bank transfer via /v3/transfers.

        ✅ Required Fields in Payload:
        - `account_bank` (str): Bank code (e.g., '044' for GTBank)
        - `account_number` (str): Recipient's account number
        - `amount` (float): Amount to send
        - `currency` (str): Currency (e.g., "NGN")
        - `narration` (str): Description of purpose
        - `reference` (str): Unique transfer reference
        - `debit_currency` (str): e.g. "NGN"
        - `callback_url` (optional): Webhook notification URL

        🔁 Sample Request:
        {
            "account_bank": "044",
            "account_number": "0690000031",
            "amount": 5000,
            "narration": "Vendor payout",
            "currency": "NGN",
            "reference": "unique-ref-001",
            "callback_url": "https://yourdomain.com/webhook",
            "debit_currency": "NGN"
        }

        ✅ Sample Response:
        {
            "message": "Transfer initiated",
            "data": {
                "id": 2198381,
                "account_number": "0690000031",
                "bank_code": "044",
                "full_name": "DOE JOHN",
                "date_created": "2024-06-16T12:00:00.000Z",
                "currency": "NGN",
                "amount": 5000,
                "fee": 10,
                "status": "NEW",
                "reference": "unique-ref-001"
            }
        }

        Returns:
            dict: Flutterwave transfer response
        """
        # Create Recipient
        if not payload.recipient_code:
            create_recipient_dto = CreateRecipientRequest(type="nuban", name=payload.fullname,
                                                          account_number=payload.account_number,
                                                          bank_code=payload.account_bank, currency=payload.currency)

            created_recipient = await self._create_recipient(create_recipient_dto)
            payload.recipient_code = created_recipient.data.recipient_code

        payload_dict = payload.model_dump()
        payload_dict["recipient"] = payload.recipient_code
        response = await httpx_client.post(f"{self.base_url}/transfers", headers=self.headers,
                                           json=payload_dict)
        response.raise_for_status()
        return BankTransferResponse(**response.json())

    async def retry_failed_bank_transfer(self, transfer_ref_id: str) -> GenericPaymentGatewayResponse:
        """
        Resends a webhook notification for a previously failed or hanging transfer.

        ✅ Required:
        - `transfer_ref_id` (str): The unique transfer reference

        ✅ Sample Response:
        {
            "status": "success",
            "message": "Transfer webhook resent"
        }

        Returns:
            dict: Webhook retry result
        """
        url = f"{self.base_url}/transfers/{transfer_ref_id}/resend-hook"
        response = await httpx_client.post(url, headers=self.headers)
        response.raise_for_status()
        return GenericPaymentGatewayResponse(**response.json())

    async def get_transfer_fee(self, payload: TransferFeeRequest) -> TransferFeeResponse:
        """
        Fetches the estimated Flutterwave transfer fee using /v3/transfers/fee.

        ✅ Required Query Params:
        - `amount` (float): Amount to send
        - `currency` (str): Currency (default: "NGN")

        🔁 Sample Request:
        /transfers/fee?amount=5000&currency=NGN

        ✅ Sample Response:
        {
            "status": "success",
            "message": "Fee fetched",
            "data": {
                "currency": "NGN",
                "amount": 5000,
                "fee": 10
            }
        }

        Returns:
            dict: Fee estimate
        """
        url = f"{self.base_url}/transfers/fee"
        response = await httpx_client.get(url, headers=self.headers, params=payload.model_dump())
        response.raise_for_status()
        return TransferFeeResponse(**response.json())

    async def get_all_country_banks(self, country_code: str) -> CountryBanksResponse:
        """
        Gets a list of all banks in a given country using /v3/banks/{country_code}.

        ✅ Required:
        - `country_code` (str): ISO country code, e.g., "NG" for Nigeria

        ✅ Sample Response:
        {
            "status": "success",
            "message": "Banks retrieved",
            "data": [
                {
                    "id": 1,
                    "code": "044",
                    "name": "GTBank"
                },
                ...
            ]
        }

        Returns:
            dict: List of banks
        """
        url = f"{self.base_url}/banks/{country_code}"
        response = await httpx_client.get(url, headers=self.headers)
        response.raise_for_status()
        return CountryBanksResponse(**response.json())

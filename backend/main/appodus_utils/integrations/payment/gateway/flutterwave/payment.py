from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger

from httpx import AsyncClient
from kink import di, inject

from main.app.config.settings import IntegratedPlatform, settings
from main.appodus_utils.integrations.payment.gateway.interface import IPaymentGateway
from main.appodus_utils.integrations.payment.gateway.models import (PaymentInitRequest, RefundRequest, BankTransferRequest,
                                                          BankTransferResponse, GenericPaymentGatewayResponse,
                                                          TransferFeeResponse, CountryBanksResponse, TransferFeeRequest)
from main.appodus_utils.integrations.payment.gateway.paystack.models import CreateRecipientRequest, CreateRecipientResponse

httpx_client: AsyncClient = di[AsyncClient]
logger: Logger = di["logger"]


@inject
class FlutterwavePaymentGateway(IPaymentGateway):

    def __init__(self):
        self.base_url = settings.FLUTTERWAVE_BASE_URL
        self.headers = {"Authorization": f"Bearer {settings.FLUTTERWAVE_SECRET_KEY}", "Content-Type": "application/json",
                        "Accept": "application/json"}
    @property
    def platform(self) -> IntegratedPlatform:
        return IntegratedPlatform.FLUTTERWAVE

    async def initialize_payment(self, payment_request: PaymentInitRequest) -> str:
        """
        Initializes a new payment session using Flutterwave /v3/payments.

        ✅ Required Fields in Payload:
        - `tx_ref` (str): Unique transaction reference
        - `amount` (str or float): Amount to be paid
        - `currency` (str): Currency code (e.g. "NGN")
        - `redirect_url` (str): URL to redirect to after payment
        - `customer.email` (str)
        - `customer.phonenumber` (str)
        - `customer.name` (str)
        - `customizations.title` (str)
        - `customizations.description` (str)

        🔁 Sample Request:
        {
            "tx_ref": "unique_tx_ref_123",
            "amount": "1000",
            "currency": "NGN",
            "redirect_url": "https://yourdomain.com/payment-callback",
            "customer": {
                "email": "customer@email.com",
                "phonenumber": "08012345678",
                "name": "Customer Name"
            },
            "customizations": {
                "title": "Payment for Property",
                "description": "Downpayment for Plot 4A"
            }
        }

        ✅ Sample Response (partial):
        {
            "status": "success",
            "message": "Payment link created",
            "data": {
                "link": "https://checkout.flutterwave.com/link/tx-123abc"
            }
        }

        Returns:
            str: Payment checkout URL
        """
        payload_dict = payment_request.model_dump(exclude_none=True)

        response = await httpx_client.post(f"{self.base_url}/payments", headers=self.headers, json=payload_dict)

        response.raise_for_status()
        response_data = GenericPaymentGatewayResponse(**response.json())
        return response_data.data["link"]

    async def verify_payment(self, reference: str) -> GenericPaymentGatewayResponse:
        """
        Verifies a transaction via /v3/transactions/{reference}/verify.

        ✅ Required:
        - `reference` (str): Unique transaction reference ID

        ✅ Sample Response:
        {
            "status": "success",
            "message": "Transaction fetched successfully",
            "data": {
                "id": 334,
                "tx_ref": "unique_tx_ref_123",
                "flw_ref": "FLW-M03K-3021a2",
                "amount": 1000,
                "currency": "NGN",
                "status": "successful",
                "payment_type": "card",
                ...
            }
        }

        Returns:
            dict: Verification result
        """
        response = await httpx_client.get(f"{self.base_url}/transactions/{reference}/verify", headers=self.headers)
        response.raise_for_status()
        return GenericPaymentGatewayResponse(**response.json())

    async def refund_transaction(self, payload: RefundRequest) -> GenericPaymentGatewayResponse:
        """
        Issues a refund using /v3/refunds.

        ✅ Required Fields:
        - `transaction_id` (str): ID of original transaction
        - `amount` (float): Refund amount (can be partial)

        🔁 Sample Request:
        {
            "transaction_id": "1234567",
            "amount": 1000,
            "comments": "Customer changed mind"
        }

        ✅ Sample Response:
        {
            "status": "success",
            "message": "Refund Queued Successfully",
            "data": {
                "id": 122,
                "status": "pending"
            }
        }

        Returns:
            dict: Refund status
        """
        response = await httpx_client.post(f"{self.base_url}/refunds", headers=self.headers, json=payload)
        response.raise_for_status()
        return GenericPaymentGatewayResponse(**response.json())

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
                "created_at": "2023-06-01T12:00:00.000Z",
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
                "created_at": "2024-06-16T12:00:00.000Z",
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

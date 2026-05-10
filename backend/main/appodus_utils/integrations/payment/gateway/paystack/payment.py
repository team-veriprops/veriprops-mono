from httpx import AsyncClient
from kink import di, inject

from main.app.config.settings import IntegratedPlatform, settings
from main.appodus_utils.exception.exceptions import NotImplementedException
from main.appodus_utils.integrations.payment.gateway.interface import IPaymentGateway
from main.appodus_utils.integrations.payment.gateway.models import (PaymentInitRequest, RefundRequest, BankTransferRequest,
                                                          BankTransferResponse, GenericPaymentGatewayResponse,
                                                          TransferFeeResponse, CountryBanksResponse, TransferFeeRequest)
from main.appodus_utils.integrations.payment.gateway.paystack.mapper import PaystackMapper
from main.appodus_utils.integrations.payment.gateway.paystack.models import (
    CreateRecipientRequest,
    CreateRecipientResponse,
    PaystackBankTransferChargeRequest,
    PaystackBankTransferResult,
)

httpx_client: AsyncClient = di[AsyncClient]


@inject
class PaystackPaymentGateway(IPaymentGateway):

    def __init__(self):
        self.base_url = settings.PAYSTACK_BASE_URL
        self.headers = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}", "Content-Type": "application/json",
                        "Accept": "application/json"}
    @property
    def platform(self) -> IntegratedPlatform:
        return IntegratedPlatform.PAYSTACK

    async def initialize_payment(self, payment_request: PaymentInitRequest) -> str:
        """
        Initializes a payment session using Paystack's `/transaction/initialize` endpoint.

        ✅ Required Fields:
        - `email` (str): Customer email
        - `amount` (int): Amount in kobo (e.g., 500000 for ₦5000)

        🔁 Sample Request:
        {
            "email": "buyer@email.com",
            "amount": 500000,
            "metadata": {
                "property_id": "PLOT-21-A1",
                "buyer_name": "Kingsley"
            }
        }

        ✅ Sample Response (partial):
        {
            "status": true,
            "data": {
                "authorization_url": "https://checkout.paystack.com/abc123",
                "reference": "abc123xyz"
            }
        }

        Returns:
            str: Paystack checkout URL
        """

        paystack_payload = PaystackMapper.to_init_payment_dto(payment_request)
        payload_dict = paystack_payload.model_dump(exclude_none=True)

        print("payload_dict: ", payload_dict)

        response = await httpx_client.post(f"{self.base_url}/transaction/initialize", headers=self.headers,
                                           json=payload_dict)

        response.raise_for_status()

        print("response: ", response.json())
        response_data = GenericPaymentGatewayResponse(**response.json())
        return response_data.data.get("authorization_url")

    async def verify_payment(self, reference: str) -> GenericPaymentGatewayResponse:
        """
        Verifies a transaction using `/transaction/verify/{reference}`.

        ✅ Required:
        - `reference` (str): Transaction reference

        ✅ Sample Response:
        {
            "status": true,
            "data": {
                "amount": 500000,
                "currency": "NGN",
                "status": "success",
                "paid_at": "2024-06-16T12:00:00.000Z",
                ...
            }
        }

        Returns:
            PaymentVerificationResponse
        """
        response = await httpx_client.get(f"{self.base_url}/transaction/verify/{reference}", headers=self.headers)
        response.raise_for_status()
        return GenericPaymentGatewayResponse(**response.json())

    async def refund_transaction(self, payload: RefundRequest) -> GenericPaymentGatewayResponse:
        """
        Issues a refund using `/refund`.

        ✅ Required Fields:
        - `transaction` (str): Transaction reference or ID
        - `amount` (optional): Amount in kobo (for partial refunds)

        ✅ Sample Response:
        {
            "status": true,
            "message": "Refund queued successfully",
            "data": {
                "id": 101,
                "status": "pending"
            }
        }

        Returns:
            RefundResponse
        """
        payload_dict = payload.model_dump()
        payload_dict["amount"] = int(payload.amount * 100)  # in kobo
        payload_dict["transaction"] = payload.transaction_id
        payload_dict["reason"] = payload.comments
        response = await httpx_client.post(f"{self.base_url}/refund", headers=self.headers, json=payload_dict)
        response.raise_for_status()
        return GenericPaymentGatewayResponse(**response.json())

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
        # TODO: calc using API cost documentation
        raise NotImplementedException("Feature not natively available in Paystack client.")

    async def charge_bank_transfer(
        self,
        payload: PaystackBankTransferChargeRequest,
    ) -> PaystackBankTransferResult:
        """Create a one-time virtual account for NGN bank transfer via POST /charge.

        Returns bank name, account number, and expiry so the frontend can
        display transfer instructions without redirecting to a checkout page.
        """
        payload_dict = payload.model_dump(exclude_none=True)
        response = await httpx_client.post(
            f"{self.base_url}/charge",
            headers=self.headers,
            json=payload_dict,
        )
        response.raise_for_status()
        data = response.json().get("data", {})
        return PaystackBankTransferResult(
            reference=data.get("reference", payload.reference or ""),
            bank=data.get("bank", ""),
            account_number=data.get("account_number", ""),
            account_name=data.get("account_name"),
            expiry_date=data.get("expiry_date"),
        )

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

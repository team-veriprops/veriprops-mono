from typing import Dict, Any
from typing import Optional

from main.appodus_utils import Object
from pydantic import Field, EmailStr

from main.appodus_utils.db.types.money import TransactionCurrency


class GenericPaymentGatewayResponse(Object):
    status: str | bool | None
    message: str
    data: Optional[Dict[str, str]]  # e.g., {"link": "https://checkout.flutterwave.com/..."}


# initialize_payment – Create Payment Session
class CustomerInfo(Object):
    email: str
    phonenumber: str
    name: str


class Customizations(Object):
    title: str
    description: str


class PaymentInitRequest(Object):
    tx_ref: str
    amount: float
    currency: TransactionCurrency = Field(..., description="E.g. NGN, USD")
    redirect_url: str
    customer: CustomerInfo
    customizations: Customizations
    metadata: Optional[Dict[str, Any]] = None


# refund_transaction – Refund API
class RefundRequest(Object):
    transaction_id: str
    amount: float
    comments: Optional[str] = Field(None, description="Reason for refund")


# initialize_bank_transfer – Send Money to Bank
class BankTransferRequest(Object):
    account_bank: str = Field(..., description="Bank code (e.g., 044 for GTBank)")
    account_number: str
    amount: float
    narration: str
    currency: TransactionCurrency
    reference: str
    callback_url: Optional[str] = None
    debit_currency: Optional[str] = None
    fullname: str
    recipient_code:  Optional[str] = None


class BankTransferResponseData(Object):
    id: int
    account_number: str
    bank_code: str
    full_name: Optional[str]
    created_at: Optional[str]
    currency: TransactionCurrency
    amount: float
    fee: Optional[float]
    status: str
    reference: str


class BankTransferResponse(Object):
    message: str
    data: BankTransferResponseData


# get_transfer_fee
class TransferFeeRequest(Object):
    amount: float
    currency: TransactionCurrency


class TransferFeeResponseData(Object):
    currency: TransactionCurrency
    amount: float
    fee: float


class TransferFeeResponse(Object):
    status: str
    message: str
    data: TransferFeeResponseData


# get_all_country_banks
class Bank(Object):
    id: int
    code: str
    name: str


class CountryBanksResponse(Object):
    status: str
    message: str
    data: list[Bank]

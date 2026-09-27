from abc import ABC, abstractmethod
from typing import Optional

from main.app.config.settings import IntegratedPlatform
from main.appodus_utils.integrations.payment.gateway.models import (
    BankTransferRequest,
    BankTransferResponse,
    CountryBanksResponse,
    GatewayCharge,
    GenericPaymentGatewayResponse,
    HostedCheckoutRequest,
    TransferFeeRequest,
    TransferFeeResponse,
)


class IPaymentGateway(ABC):
    """One payment provider behind a provider-neutral contract.

    Collection is three calls: open a hosted checkout, look a charge up by our reference, and
    refund it. Every failure to reach or satisfy the provider raises ``IntegrationException``
    with a sentence of our own; the provider's text goes to the log only.
    """

    @property
    @abstractmethod
    def platform(self) -> IntegratedPlatform:
        pass

    @abstractmethod
    async def create_hosted_checkout(self, request: HostedCheckoutRequest) -> str:
        """The URL of the gateway's hosted page where the customer pays."""

    @abstractmethod
    async def get_charge(self, reference: str) -> Optional[GatewayCharge]:
        """The charge for our ``reference``, or ``None`` when the gateway has never charged it."""

    @abstractmethod
    async def refund_charge(self, reference: str, amount_minor: int, reason: Optional[str]) -> None:
        """Ask the gateway to return ``amount_minor`` of the charge to the customer.

        Gateways queue refunds, so success here means "accepted", not "settled"."""

    @abstractmethod
    async def initialize_bank_transfer(self, payload: BankTransferRequest) -> BankTransferResponse:
        pass

    @abstractmethod
    async def retry_failed_bank_transfer(self, transfer_ref_id: str) -> GenericPaymentGatewayResponse:
        pass

    @abstractmethod
    async def get_transfer_fee(self, payload: TransferFeeRequest) -> TransferFeeResponse:
        pass

    @abstractmethod
    async def get_all_country_banks(self, country_code: str) -> CountryBanksResponse:
        pass

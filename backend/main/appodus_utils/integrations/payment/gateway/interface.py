from abc import ABC, abstractmethod
from typing import List, Optional

from main.app.config.settings import IntegratedPlatform
from main.appodus_utils.db.types.money import TransactionCurrency
from main.appodus_utils.integrations.payment.gateway.models import (
    GatewayAccount,
    GatewayBank,
    GatewayCharge,
    GatewayTransfer,
    HostedCheckoutRequest,
    TransferRequest,
)


class ITransferGateway(ABC):
    """Paying out to a bank account, behind a provider-neutral contract.

    Every failure to reach or satisfy the provider raises ``IntegrationException`` with a
    sentence of our own. A provider that answered "no" raises its subclass ``GatewayDeclined``;
    anything else (unreachable, a 5xx) means the outcome is unknown and only a lookup by our
    reference can settle it.
    """

    @abstractmethod
    async def list_banks(self, currency: TransactionCurrency) -> List[GatewayBank]:
        """The banks a transfer in *currency* can be sent to."""

    @abstractmethod
    async def resolve_account(self, bank_code: str, account_number: str) -> Optional[GatewayAccount]:
        """The account as the bank holds it, or ``None`` when the bank knows no such account."""

    @abstractmethod
    async def quote_fee(self, amount_minor: int, currency: TransactionCurrency) -> int:
        """What the gateway charges, in minor units, to transfer *amount_minor*."""

    @abstractmethod
    async def send_transfer(self, request: TransferRequest) -> GatewayTransfer:
        """Queue the transfer. Success means "accepted"; the outcome arrives later."""

    @abstractmethod
    async def get_transfer(self, reference: str) -> Optional[GatewayTransfer]:
        """The transfer under our *reference*, or ``None`` when the gateway never took one."""


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

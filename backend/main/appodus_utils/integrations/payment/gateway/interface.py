from abc import abstractmethod, ABC

from main.app.config.settings import IntegratedPlatform
from main.appodus_utils.integrations.payment.gateway.models import (PaymentInitRequest, BankTransferRequest, BankTransferResponse,
                                                          GenericPaymentGatewayResponse, TransferFeeResponse,
                                                          CountryBanksResponse, RefundRequest, TransferFeeRequest)


class IPaymentGateway(ABC):
    @property
    @abstractmethod
    def platform(self) -> IntegratedPlatform:
        pass

    @abstractmethod
    async def initialize_payment(self, payload: PaymentInitRequest) -> str:
        pass

    @abstractmethod
    async def verify_payment(self, reference: str) -> GenericPaymentGatewayResponse:
        pass

    @abstractmethod
    async def refund_transaction(self, payload: RefundRequest) -> GenericPaymentGatewayResponse:
        pass

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

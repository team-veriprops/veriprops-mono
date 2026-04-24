from typing import List

from kink import inject

from main.app.config.bootstrap import di_bootstrap
from main.app.config.settings import IntegratedPlatform, settings
from main.appodus_utils.integrations.interface import IWebhookHandler, BaseWebhookHandler
from main.appodus_utils.integrations.payment.gateway.interface import IPaymentGateway

di_bootstrap.register_all_subclasses(BaseWebhookHandler)
di_bootstrap.register_all_subclasses(IPaymentGateway)


# @inject
# class EscrowGatewayFactory:
#     def __init__(self, gateways: List[IEscrowGateway]):
#         self._gateways = gateways
#         self._factory = {}
#         self._init_factory()
#
#     def _init_factory(self):
#         for gateway in self._gateways:
#             self._factory[gateway.platform] = gateway
#
#     def get_gateway(self, platform: str) -> IEscrowGateway:
#         return self._factory.get(platform)
#
#     def get_gateways(self) -> List[IEscrowGateway]:
#         return self._gateways


@inject
class PaymentGatewayFactory:
    def __init__(self, gateways: List[IPaymentGateway]):
        self._gateways = gateways
        self._factory = {}
        self._init_factory()

    def _init_factory(self):
        for gateway in self._gateways:
            self._factory[gateway.platform] = gateway

    def get_gateway(self, platform: IntegratedPlatform) -> IPaymentGateway:
        return self._factory.get(platform)

    def get_default_gateway(self) -> IPaymentGateway:
        return self._factory.get(settings.ACTIVE_PAYMENT_METHOD)

    def get_gateways(self) -> List[IPaymentGateway]:
        return self._gateways


@inject
class WebhookHandlerFactory:
    def __init__(self, handlers: List[BaseWebhookHandler]):
        self._handlers = handlers
        self._factory = {}
        self._init_factory()

    def _init_factory(self):
        for handler in self._handlers:
            self._factory[handler.platform] = handler

    def get_handler(self, platform: IntegratedPlatform) -> IWebhookHandler:
        return self._factory.get(platform)

    def get_handlers(self) -> List[IWebhookHandler]:
        return self._handlers

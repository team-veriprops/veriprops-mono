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
    """Routes an inbound webhook to the handler that owns its platform.

    The table is **rebuilt on a miss** rather than fixed at construction. Handlers are
    discovered through ``BaseWebhookHandler.__subclasses__()``, so the set depends on
    which integration packages have been imported at that instant — and the app's entry
    point imports the webhook router before some of them. A fixed table meant a handler
    that loaded later was invisible forever, and its endpoint answered "platform not
    supported" with nothing in the logs to say why (the WhatsApp channel shipped that
    way). Rebuilding costs one pass over the subclasses, and only on a miss.
    """

    def __init__(self, handlers: List[BaseWebhookHandler]):
        self._handlers = handlers
        self._factory = {}
        self._init_factory()

    def _init_factory(self):
        for handler in self._handlers:
            self._factory[handler.platform] = handler

    def _rediscover(self) -> None:
        """Pick up handlers whose packages were imported after this factory was built."""
        self._handlers = di_bootstrap.register_all_subclasses(BaseWebhookHandler)
        self._init_factory()

    def get_handler(self, platform: IntegratedPlatform) -> IWebhookHandler:
        handler = self._factory.get(platform)
        if handler is None:
            self._rediscover()
            handler = self._factory.get(platform)
        return handler

    def get_handlers(self) -> List[IWebhookHandler]:
        return self._handlers

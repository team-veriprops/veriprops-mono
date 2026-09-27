from typing import List, Optional

from kink import inject

from main.app.config.bootstrap import di_bootstrap
from main.app.config.settings import IntegratedPlatform, settings
from main.appodus_utils.integrations.exception.exceptions import IntegrationFatalException
from main.appodus_utils.integrations.interface import IWebhookHandler, BaseWebhookHandler
from main.appodus_utils.integrations.payment.gateway.interface import IPaymentGateway, ITransferGateway
from main.appodus_utils.integrations.payment.gateway.stub import StubTransferGateway

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
    """The payment gateways, by platform.

    Like the webhook factory below, the table is rebuilt on a miss: gateways are discovered
    through ``IPaymentGateway.__subclasses__()``, so one whose package loaded after this
    factory was built would otherwise be invisible for the life of the process.
    """

    def __init__(self, gateways: List[IPaymentGateway]):
        self._gateways = gateways
        self._factory = {}
        self._init_factory()

    def _init_factory(self):
        for gateway in self._gateways:
            self._factory[gateway.platform] = gateway

    def for_platform(self, platform: IntegratedPlatform) -> IPaymentGateway:
        """The gateway that holds charges on *platform*; a missing one is a deployment fault."""
        gateway = self._factory.get(platform)
        if gateway is None:
            self._gateways = di_bootstrap.register_all_subclasses(IPaymentGateway)
            self._init_factory()
            gateway = self._factory.get(platform)
        if gateway is None:
            raise IntegrationFatalException(f"No payment gateway is registered for {platform.value}.")
        return gateway

    def active(self) -> IPaymentGateway:
        """The gateway new charges go to (settings.ACTIVE_PAYMENT_METHOD)."""
        platform = settings.ACTIVE_PAYMENT_METHOD.integrated_platform
        if platform is None:
            raise IntegrationFatalException(
                f"{settings.ACTIVE_PAYMENT_METHOD.value} has no payment integration."
            )
        return self.for_platform(platform)

    def transfer_platform(self) -> Optional[IntegratedPlatform]:
        """The platform new bank accounts are resolved with, and so later paid through;
        ``None`` under PAYMENT_STUB_MODE."""
        return None if settings.PAYMENT_STUB_MODE else self.active().platform

    def transfers(self, platform: Optional[IntegratedPlatform]) -> ITransferGateway:
        """The gateway that pays an account resolved with *platform*.

        A bank code is only meaningful to the gateway whose list it came from, so a payout
        leaves through its account's own platform. Under PAYMENT_STUB_MODE it is always the
        stub, so no automated run can reach a live gateway."""
        if settings.PAYMENT_STUB_MODE:
            return _STUB_TRANSFERS
        if platform is None:
            raise IntegrationFatalException(
                "This bank account was never resolved with a payment gateway; it must be added again."
            )
        gateway = self.for_platform(platform)
        if not isinstance(gateway, ITransferGateway):
            raise IntegrationFatalException(f"{platform.value} cannot send transfers.")
        return gateway

    def get_gateways(self) -> List[IPaymentGateway]:
        return self._gateways


_STUB_TRANSFERS = StubTransferGateway()


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

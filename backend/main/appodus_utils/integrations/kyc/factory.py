from typing import List

from kink import inject

from main.app.config.bootstrap import di_bootstrap
from main.app.config.settings import settings
from main.appodus_utils.integrations.kyc.interface import IKycProvider
from main.appodus_utils.integrations.kyc.models import KycProvider

di_bootstrap.register_all_subclasses(IKycProvider)


@inject
class KycProviderFactory:
    """Resolves the active KYC provider from ``settings.KYC_PROVIDER``.

    Every ``IKycProvider`` subclass is registered so the selection is a runtime
    setting, not a wiring change. The deterministic StubKycProvider is the
    default in local/test/dev.
    """

    def __init__(self, providers: List[IKycProvider]):
        self._providers = providers
        self._factory = {p.platform: p for p in providers}

    def get_active_provider(self) -> IKycProvider:
        selected = KycProvider(settings.KYC_PROVIDER)
        return self._factory.get(selected)

    def get_provider(self, provider: KycProvider) -> IKycProvider:
        return self._factory.get(provider)

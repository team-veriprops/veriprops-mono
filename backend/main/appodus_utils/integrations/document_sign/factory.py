from typing import List

from kink import inject

from main.app.config.bootstrap import register_all_subclasses
from main.app.config.settings import settings
from main.appodus_utils.integrations.document_sign.interface import IDocumentSignProvider

register_all_subclasses(IDocumentSignProvider)


@inject
class DocumentSignProviderFactory:
    def __init__(self, providers: List[IDocumentSignProvider]):
        self._providers = providers
        self._factory = {}
        self._init_factory()

    def _init_factory(self):
        for provider in self._providers:
            self._factory[provider.platform] = provider

    def get_active_provider(self) -> IDocumentSignProvider:
        return self._factory.get(settings.ACTIVE_DOCUMENT_SIGN_PLATFORM)

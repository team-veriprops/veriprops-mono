from typing import List

from kink import di, inject

from main.app.config.bootstrap import di_bootstrap
from main.app.config.settings import settings
from main.appodus_utils.integrations.document_storage.interface import IDocumentStorageProvider
from main.appodus_utils.integrations.document_storage.stub.stub_storage import StubDocumentStorageProvider

di_bootstrap.register_all_subclasses(IDocumentStorageProvider)


@inject
class DocumentStorageProviderFactory:
    def __init__(self, providers: List[IDocumentStorageProvider]):
        self._providers = providers
        self._factory = {}
        self._init_factory()

    def _init_factory(self):
        for provider in self._providers:
            self._factory[provider.platform] = provider

    def get_active_provider(self) -> IDocumentStorageProvider:
        return self._factory.get(settings.AWS_S3_PLATFORM_NAME)

    def storage(self) -> IDocumentStorageProvider:
        """Where documents go: the deterministic stub under DOCUMENT_STORAGE_STUB_MODE (no
        bucket, no credentials — tests and local), else the configured store."""
        if settings.DOCUMENT_STORAGE_STUB_MODE:
            return di[StubDocumentStorageProvider]
        return self.get_active_provider()

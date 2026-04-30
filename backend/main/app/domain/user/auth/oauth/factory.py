from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger

from typing import List

from kink import di, inject

from main.app.domain.user.auth.oauth.providers.models import SocialAuthProvider
from main.appodus_utils.config.bootstrap import BaseDiBootstrap
from main.app.domain.user.auth.oauth.interface import ISocialAuthProvider

from main.appodus_utils.exception.exceptions import NotImplementedException

BaseDiBootstrap.register_all_subclasses(ISocialAuthProvider)
logger: Logger = di["logger"]


@inject
class SocialAuthProviderFactory:
    def __init__(self, providers: List[ISocialAuthProvider] = di[List[ISocialAuthProvider]]):
        self._providers = providers
        self._factory = {}
        self._init_factory()

    def _init_factory(self):
        logger.debug("Initializing SocialAuthProviders...")
        for provider in self._providers:
            logger.debug(f"... initialized: {provider.platform} -> {provider}")
            self._factory[provider.platform] = provider

    def get_auth_provider(self, provider: SocialAuthProvider) -> ISocialAuthProvider:
        auth_provider = self._factory.get(provider)

        if not auth_provider:
            msg = f"Unsupported provider: {provider}"
            logger.error(msg)
            raise NotImplementedException(message=msg)

        return auth_provider

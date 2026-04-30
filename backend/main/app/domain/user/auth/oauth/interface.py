from abc import ABC, abstractmethod
from typing import Optional

from main.app.domain.user.auth.oauth.providers.models import SocialAuthProvider, \
    OAuthCallbackRequestDto, SocialLoginUserInfoDto
from starlette.requests import Request


class ISocialAuthProvider(ABC):
    @property
    @abstractmethod
    def platform(self) -> SocialAuthProvider:
        pass

    @abstractmethod
    async def initialize(self, request: Request, intent: Optional[str] = None) -> str:
        pass

    @abstractmethod
    async def verify(self, payload: OAuthCallbackRequestDto, request: Request) -> SocialLoginUserInfoDto:
        pass

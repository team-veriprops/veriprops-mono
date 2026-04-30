from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger
import json
from typing import Optional, List

from kink import inject, di

from main.app.domain.user.auth.oauth.models import OAuthIdentity, CreateOAuthIdentityDto, SearchOAuthIdentityDto
from main.app.domain.user.auth.oauth.providers.models import SocialAuthProvider
from main.app.domain.user.auth.oauth.repo import OAuthIdentityRepo
from main.app.domain.user.auth.session.service import SessionService
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional

logger: Logger = di['logger']


@inject
@decorate_all_methods(transactional(), exclude=[])
@decorate_all_methods(method_trace_logger, exclude=[])
class OAuthIdentityService:
    def __init__(self,
                 oauth_repo: OAuthIdentityRepo,
                 session_service: SessionService,
                 ):
        self._oauth_repo = oauth_repo
        self._session_service = session_service

    async def get_oauth_identity(
            self, provider: SocialAuthProvider, subject: str
    ) -> Optional[OAuthIdentity]:
        return await self._oauth_repo.get_by_provider_subject(provider, subject)

    async def link_oauth(
            self,
            user_id: str,
            provider: SocialAuthProvider,
            subject: str,
            email: Optional[str] = None,
            raw_profile: Optional[dict] = None,
    ) -> OAuthIdentity:
        existing = await self._oauth_repo.get_by_provider_subject(provider, subject)
        if existing:
            return existing
        dto = CreateOAuthIdentityDto(
            user_id=user_id,
            provider=provider,
            subject=subject,
            email=email,
            raw_profile=json.dumps(raw_profile) if raw_profile else None,
        )
        await self._oauth_repo.create(dto)
        return await self._oauth_repo.get_by_provider_subject(provider, subject)

    async def list_linked_providers(self, user_id: str) -> List[str]:
        rows = await self._oauth_repo.get_by_criterion(
            SearchOAuthIdentityDto(user_id=user_id)
        )
        return [r.provider for r in rows]

    async def unlink_oauth(self, user_id: str, provider: SocialAuthProvider) -> None:
        await self._oauth_repo.soft_delete_by_criterion(
            SearchOAuthIdentityDto(user_id=user_id, provider=provider.value)
        )

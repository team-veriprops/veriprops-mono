from typing import Type, Optional

from kink import inject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.user.auth.oauth.models import QueryOAuthIdentityDto, UpdateOAuthIdentityDto, OAuthIdentity, \
    CreateOAuthIdentityDto, SearchOAuthIdentityDto
from main.app.domain.user.auth.oauth.providers.models import SocialAuthProvider
from main.appodus_utils.db.repo import GenericRepo


@inject
class OAuthIdentityRepo(
    GenericRepo[
        OAuthIdentity,
        CreateOAuthIdentityDto,
        UpdateOAuthIdentityDto,
        QueryOAuthIdentityDto,
        SearchOAuthIdentityDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[OAuthIdentity] = OAuthIdentity,
        query_dto: Type[QueryOAuthIdentityDto] = QueryOAuthIdentityDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def get_by_provider_subject(
        self, provider: SocialAuthProvider, subject: str
    ) -> Optional[OAuthIdentity]:
        stmt = select(OAuthIdentity).where(
            OAuthIdentity.deleted.is_(False),
            OAuthIdentity.provider == provider.value,
            OAuthIdentity.subject == subject,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

from typing import Optional

from sqlalchemy import Column, String, Index

from main.appodus_utils.db.models import live_unique_index

from main.app.domain.user.auth.oauth.providers.models import SocialAuthProvider
from main.appodus_utils import InternalPageRequest, BaseQueryDto, Object, BaseEntity


class OAuthIdentity(BaseEntity):
    __tablename__ = "oauth_identities"

    user_id = Column(String(36), nullable=False, index=True)
    provider = Column(String(16), nullable=False)
    subject = Column(String(255), nullable=False)  # provider's stable user id
    email = Column(String(254), nullable=True)
    raw_profile = Column(String, nullable=True)  # JSON-encoded profile snapshot

    __table_args__ = (
        # Live identities only, so an unlinked provider account can be linked again.
        live_unique_index("uq_oauth_provider_subject", "provider", "subject"),
        Index("ix_oauth_user", "user_id"),
    )


class CreateOAuthIdentityDto(Object):
    user_id: str
    provider: SocialAuthProvider
    subject: str
    email: Optional[str] = None
    raw_profile: Optional[str] = None


class UpdateOAuthIdentityDto(Object):
    email: Optional[str] = None
    raw_profile: Optional[str] = None


class SearchOAuthIdentityDto(InternalPageRequest, BaseQueryDto):
    user_id: Optional[str] = None
    provider: Optional[str] = None
    subject: Optional[str] = None


class QueryOAuthIdentityDto(BaseQueryDto):
    user_id: Optional[str] = None
    provider: Optional[str] = None
    subject: Optional[str] = None
    email: Optional[str] = None


class LinkOAuthDto(Object):
    provider: SocialAuthProvider

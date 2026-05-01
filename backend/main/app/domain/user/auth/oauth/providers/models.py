import enum
from typing import Optional

from main.appodus_utils import Object


class SocialAuthProvider(str, enum.Enum):
    APPLE = "apple"
    FACEBOOK = "facebook"
    GOOGLE = "google"


class OAuthFlowMode(str, enum.Enum):
    AUTH = "auth"   # signup / login
    LINK = "link"   # link to currently authenticated account


class OAuthRequestStoredState(Object):
    code_verifier: str
    intent: str
    frontend_origin: str
    mode: OAuthFlowMode = OAuthFlowMode.AUTH
    # Set when mode=LINK so the callback can attach the identity to the right
    # user even if cookies are stripped by the provider's redirect chain.
    link_user_id: Optional[str] = None


class OAuthCallbackRequestDto(Object):
    code: str
    code_verifier: str
    redirect_uri: str


class SocialLoginUserInfoDto(Object):
    provider: SocialAuthProvider
    id: Optional[str] = None
    email: Optional[str] = None
    email_verified: Optional[bool] = False
    firstname: Optional[str] = None
    lastname: Optional[str] = None
    picture: Optional[str] = None

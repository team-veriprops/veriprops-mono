import enum
from typing import Optional

from main.appodus_utils import Object


class SocialAuthProvider(str, enum.Enum):
    APPLE = "apple"
    FACEBOOK = "facebook"
    GOOGLE = "google"


class OAuthRequestStoredState(Object):
    code_verifier: str
    intent: str


class OAuthCallbackRequestDto(Object):
    code: str
    code_verifier: str


class SocialLoginUserInfoDto(Object):
    provider: SocialAuthProvider
    id: Optional[str] = None
    email: Optional[str] = None
    email_verified: Optional[bool] = False
    firstname: Optional[str] = None
    lastname: Optional[str] = None
    picture: Optional[str] = None

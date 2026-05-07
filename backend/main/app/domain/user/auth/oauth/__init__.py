from typing import Optional, Tuple

from main.app.domain.user.auth.oauth.providers.apple import AppleAuthProvider
from main.app.domain.user.auth.oauth.providers.facebook import FacebookAuthProvider
from main.app.domain.user.auth.oauth.providers.google import GoogleAuthProvider
from main.app.domain.user.auth.oauth.providers.models import SocialAuthProvider
from main.appodus_utils import Utils


def make_oauth_state(intent: Optional[str]) -> Tuple[str, dict]:
    """Return (state_token, payload) for a new OAuth round-trip.

    The state token is a random string stored in Redis (single-use, short TTL).
    The payload records the intent so the callback can assign the right persona.
    """
    state = Utils.random_str(36)
    payload = {"intent": intent if intent else "default"}
    return state, payload


def normalise_provider(provider: str) -> SocialAuthProvider:
    """Case-insensitive provider name → SocialAuthProvider. Falls back to GOOGLE."""
    try:
        return SocialAuthProvider(provider.lower())
    except ValueError:
        return SocialAuthProvider.GOOGLE

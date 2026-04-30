"""OAuth helper tests — no network."""
from main.app.domain.user.auth.oauth import make_oauth_state, normalise_provider
from main.app.domain.user.models import SocialAuthProvider


class TestMakeOauthState:
    def test_state_is_unique(self):
        a, _ = make_oauth_state(intent=None)
        b, _ = make_oauth_state(intent=None)
        assert a != b
        assert len(a) >= 30

    def test_payload_carries_intent(self):
        _, payload = make_oauth_state(intent="verify")
        assert payload["intent"] == "verify"

    def test_default_intent_when_none(self):
        _, payload = make_oauth_state(intent=None)
        assert payload["intent"] == "default"


class TestNormaliseProvider:
    def test_known_provider(self):
        assert normalise_provider("google") == SocialAuthProvider.GOOGLE

    def test_uppercase_provider(self):
        assert normalise_provider("GOOGLE") == SocialAuthProvider.GOOGLE

    def test_unknown_falls_back_to_google(self):
        assert normalise_provider("nonexistent") == SocialAuthProvider.GOOGLE

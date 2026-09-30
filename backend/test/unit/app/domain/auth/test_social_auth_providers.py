"""Social sign-in providers (§1.2): the factory hands each flow its provider, and Facebook's
code exchange yields an account only when Facebook returns an email.

Facebook is exercised over HTTP with respx: the PKCE code is exchanged for a token, the token
reads the profile, and a profile without an email — the user declined the scope, or signed
up to Facebook by phone — is refused, because an account needs an email.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest
import respx

from main.app.domain.user.auth.oauth.factory import SocialAuthProviderFactory
from main.app.domain.user.auth.oauth.providers import facebook as facebook_module
from main.app.domain.user.auth.oauth.providers.facebook import FacebookAuthProvider
from main.app.domain.user.auth.oauth.providers.models import OAuthCallbackRequestDto, SocialAuthProvider
from main.appodus_utils.exception.exceptions import AppodusBaseException, NotImplementedException

_TOKEN_URL = "https://graph.facebook.com/v22.0/oauth/access_token"
_ME_URL = "https://graph.facebook.com/me"
_CALLBACK = OAuthCallbackRequestDto(code="code-1", code_verifier="verifier-1", redirect_uri="https://app.test/cb")


class TestFactory:
    def test_hands_back_the_provider_registered_for_the_platform(self):
        google = SimpleNamespace(platform=SocialAuthProvider.GOOGLE)
        apple = SimpleNamespace(platform=SocialAuthProvider.APPLE)
        factory = SocialAuthProviderFactory(providers=[google, apple])

        assert factory.get_auth_provider(SocialAuthProvider.APPLE) is apple

    def test_an_unregistered_platform_is_refused(self):
        factory = SocialAuthProviderFactory(providers=[SimpleNamespace(platform=SocialAuthProvider.GOOGLE)])

        with pytest.raises(NotImplementedException):
            factory.get_auth_provider(SocialAuthProvider.FACEBOOK)


@pytest.fixture
def facebook(monkeypatch):
    client = httpx.AsyncClient()
    monkeypatch.setattr(facebook_module, "httpx_client", client)
    provider = object.__new__(FacebookAuthProvider)
    provider._client_id, provider._client_secret, provider._auth_base_url = "app-id", "app-secret", "https://fb.test"
    return provider


class TestFacebookVerify:
    @respx.mock
    async def test_exchanges_the_pkce_code_then_reads_the_profile(self, facebook):
        token = respx.get(_TOKEN_URL).mock(return_value=httpx.Response(200, json={"access_token": "tok-1"}))
        me = respx.get(_ME_URL).mock(return_value=httpx.Response(200, json={
            "id": "fb-1", "email": "ada@example.com", "first_name": "ada", "last_name": "obi",
        }))

        info = await facebook.verify(_CALLBACK, request=MagicMock())

        exchange = token.calls.last.request.url.params
        assert (exchange["code"], exchange["code_verifier"], exchange["redirect_uri"]) == ("code-1", "verifier-1", "https://app.test/cb")
        assert (exchange["client_id"], exchange["client_secret"]) == ("app-id", "app-secret")
        assert me.calls.last.request.url.params["access_token"] == "tok-1"
        assert (info.provider, info.id, info.email, info.email_verified) == (SocialAuthProvider.FACEBOOK, "fb-1", "ada@example.com", True)
        assert (info.firstname, info.lastname) == ("Ada", "Obi")

    @respx.mock
    async def test_a_profile_without_an_email_is_refused(self, facebook):
        respx.get(_TOKEN_URL).mock(return_value=httpx.Response(200, json={"access_token": "tok-1"}))
        respx.get(_ME_URL).mock(return_value=httpx.Response(200, json={"id": "fb-1", "first_name": "Ada"}))

        with pytest.raises(AppodusBaseException, match="did not return an email"):
            await facebook.verify(_CALLBACK, request=MagicMock())

    @respx.mock
    async def test_a_refused_code_exchange_stops_before_the_profile_is_read(self, facebook):
        respx.get(_TOKEN_URL).mock(return_value=httpx.Response(400, json={"error": {"message": "code expired"}}))
        me = respx.get(_ME_URL)

        with pytest.raises(httpx.HTTPStatusError):
            await facebook.verify(_CALLBACK, request=MagicMock())
        assert not me.called

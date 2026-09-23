"""Unit tests for revoked-session enforcement on token refresh (S6)."""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from libre_fastapi_jwt import AuthJWT
from starlette.responses import Response

from main.app.config.settings import settings
from main.app.domain.user.auth.session import controller as session_controller
from main.app.domain.user.auth.session.models import AuthSessionDto

# Every cookie a session lives in. A rejected refresh must delete all of them *on the response the
# browser receives*: a surviving refresh cookie still reads as a live session to the frontend proxy,
# which then bounces the user off the login page back into the app — an endless loop.
_SESSION_COOKIE_KEYS = {
    settings.AUTHJWT_ACCESS_COOKIE_KEY,
    settings.AUTHJWT_REFRESH_COOKIE_KEY,
    settings.AUTHJWT_ACCESS_CSRF_COOKIE_KEY,
    settings.AUTHJWT_REFRESH_CSRF_COOKIE_KEY,
}


def _request_with_refresh(token: str | None):
    # The refresh cookie is issued under the configured key (__Host-refresh_token),
    # not the bare "refresh_token" — the controller must read the configured name.
    cookie_key = settings.AUTHJWT_REFRESH_COOKIE_KEY
    return SimpleNamespace(cookies={cookie_key: token} if token else {})


def _deleted_cookie_keys(response) -> set[str]:
    """Cookie names the response instructs the browser to delete (`Max-Age=0`)."""
    return {
        header.split("=", 1)[0]
        for header in response.headers.getlist("set-cookie")
        if "max-age=0" in header.lower()
    }


class _LibraryLikeAuthorize:
    """Behaves like `AuthJWT` where it matters here: no subject until a token has been verified."""

    def __init__(self, subject: str = "u-1"):
        self._subject = subject
        self._verified = False

    async def jwt_refresh_token_required(self):
        self._verified = True

    def get_jwt_subject(self):
        return self._subject if self._verified else None


async def _rejected_refresh(monkeypatch, token: str | None):
    fake_service = MagicMock()
    fake_service.get_device_by_token_hash = AsyncMock(return_value=None)
    monkeypatch.setattr(session_controller, "session_service", fake_service)
    refresh = AsyncMock()
    monkeypatch.setattr(session_controller.JwtAuthUtils, "refresh_access_token", refresh)

    # A real AuthJWT: the defect was cookie deletions that never reached the returned response,
    # which a mocked authorize cannot show.
    response = await session_controller.refresh_session(
        _request_with_refresh(token), AuthJWT(res=Response()),
    )
    return response, refresh


class TestRefreshRevokedSession:
    async def test_revoked_session_is_rejected_with_its_cookies_deleted(self, monkeypatch):
        response, refresh = await _rejected_refresh(monkeypatch, "rt")

        assert response.status_code == 401
        assert json.loads(response.body) == {
            "error": {"code": "UNAUTHORIZED", "message": "Session has been revoked. Please sign in again."}
        }
        assert _SESSION_COOKIE_KEYS <= _deleted_cookie_keys(response)
        refresh.assert_not_awaited()

    async def test_missing_refresh_cookie_is_rejected_with_its_cookies_deleted(self, monkeypatch):
        response, refresh = await _rejected_refresh(monkeypatch, None)

        assert response.status_code == 401
        assert _SESSION_COOKIE_KEYS <= _deleted_cookie_keys(response)
        refresh.assert_not_awaited()

    async def test_refreshes_and_touches_when_device_active(self, monkeypatch):
        # model_construct bypasses field validation — this test only cares that
        # the controller forwards session_service's DTO, not its contents.
        fake_session_dto = AuthSessionDto.model_construct()
        fake_service = MagicMock()
        fake_service.get_device_by_token_hash = AsyncMock(return_value=MagicMock(id="dev-1"))
        fake_service.touch_device_session = AsyncMock()
        fake_service.build_session_dto = AsyncMock(return_value=fake_session_dto)
        monkeypatch.setattr(session_controller, "session_service", fake_service)
        refresh = AsyncMock()
        monkeypatch.setattr(session_controller.JwtAuthUtils, "refresh_access_token", refresh)

        fake_user = MagicMock()
        fake_user_service = MagicMock()
        fake_user_service.get_user_model = AsyncMock(return_value=fake_user)
        monkeypatch.setattr(session_controller, "user_service", fake_user_service)

        resp = await session_controller.refresh_session(
            _request_with_refresh("rt"), _LibraryLikeAuthorize("user-1"),
        )

        # The endpoint returns the fresh session DTO (not a bare bool) so the
        # frontend keep-alive can resync accessTokenExpiresAt after a refresh.
        assert resp.data is fake_session_dto
        refresh.assert_awaited_once()
        fake_service.touch_device_session.assert_awaited_once()
        fake_user_service.get_user_model.assert_awaited_once_with("user-1")
        fake_service.build_session_dto.assert_awaited_once_with(fake_user)


class TestRefreshReadsPersonasFromTheRecord:
    """A refresh used to copy `personas` forward from the expiring token.

    That made a persona granted mid-session invisible — a customer who applied to become an agent
    kept a token saying CUSTOMER, and the frontend route guard turned them away from the agent
    area — and, the same way round, a persona withdrawn mid-session kept working for the whole
    life of the refresh token. The claims are now read from the user record.
    """

    class _StopAfterMint(Exception):
        """Ends the request once the token has been minted; the response DTO is not the subject."""

    async def _refresh_with_record_personas(self, monkeypatch, personas):
        user = SimpleNamespace(id="u-1", user_type="USER", personas=personas, admin_sub_role=None)

        fake_session = MagicMock()
        fake_session.get_device_by_token_hash = AsyncMock(return_value=SimpleNamespace(id="d-1"))
        fake_session.touch_device_session = AsyncMock()
        fake_session.build_session_dto = AsyncMock(side_effect=self._StopAfterMint())
        monkeypatch.setattr(session_controller, "session_service", fake_session)

        fake_users = MagicMock()
        fake_users.get_user_model = AsyncMock(return_value=user)
        monkeypatch.setattr(session_controller, "user_service", fake_users)

        refresh = AsyncMock()
        monkeypatch.setattr(session_controller.JwtAuthUtils, "refresh_access_token", refresh)

        try:
            await session_controller.refresh_session(
                _request_with_refresh("rt"), _LibraryLikeAuthorize(),
            )
        except self._StopAfterMint:
            pass
        return refresh

    async def test_a_persona_granted_mid_session_reaches_the_new_token(self, monkeypatch):
        refresh = await self._refresh_with_record_personas(monkeypatch, ["CUSTOMER", "AGENT"])

        refresh.assert_awaited_once()
        assert refresh.await_args.kwargs["user_personas"] == ["CUSTOMER", "AGENT"]

    async def test_a_persona_withdrawn_mid_session_is_gone_from_the_new_token(self, monkeypatch):
        refresh = await self._refresh_with_record_personas(monkeypatch, ["CUSTOMER"])

        assert refresh.await_args.kwargs["user_personas"] == ["CUSTOMER"]


class TestRefreshVerifiesBeforeReadingTheSubject:
    """`AuthJWT` has no subject until a `*_required()` call has verified a token.

    Loading the user before minting moved `get_jwt_subject()` ahead of the verification that used
    to happen inside `refresh_access_token`, so it read `None`, looked up the user `"None"`, and
    answered **every** refresh with a 500 — silent session recovery stopped working entirely. The
    persona tests above could not see it: they mock `get_user_model`, so any subject is accepted.
    This double behaves like the library, which is the only way the ordering shows up.
    """

    async def test_the_refresh_token_is_verified_before_its_subject_is_read(self, monkeypatch):
        fake_session = MagicMock()
        fake_session.get_device_by_token_hash = AsyncMock(return_value=SimpleNamespace(id="d-1"))
        fake_session.touch_device_session = AsyncMock()
        fake_session.build_session_dto = AsyncMock(return_value=AuthSessionDto.model_construct())
        monkeypatch.setattr(session_controller, "session_service", fake_session)

        user = SimpleNamespace(id="u-1", user_type="USER", personas=["CUSTOMER"], admin_sub_role=None)
        fake_users = MagicMock()
        fake_users.get_user_model = AsyncMock(return_value=user)
        monkeypatch.setattr(session_controller, "user_service", fake_users)
        monkeypatch.setattr(session_controller.JwtAuthUtils, "refresh_access_token", AsyncMock())

        await session_controller.refresh_session(_request_with_refresh("rt"), _LibraryLikeAuthorize())

        fake_users.get_user_model.assert_awaited_once_with("u-1")

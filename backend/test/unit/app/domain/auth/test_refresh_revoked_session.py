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

        authorize = MagicMock()
        authorize.get_jwt_subject = MagicMock(return_value="user-1")
        resp = await session_controller.refresh_session(_request_with_refresh("rt"), authorize)

        # The endpoint returns the fresh session DTO (not a bare bool) so the
        # frontend keep-alive can resync accessTokenExpiresAt after a refresh.
        assert resp.data is fake_session_dto
        refresh.assert_awaited_once()
        fake_service.touch_device_session.assert_awaited_once()
        fake_user_service.get_user_model.assert_awaited_once_with("user-1")
        fake_service.build_session_dto.assert_awaited_once_with(fake_user)

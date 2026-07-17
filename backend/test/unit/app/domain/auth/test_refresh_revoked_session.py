"""Unit tests for revoked-session enforcement on token refresh (S6)."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.config.settings import settings
from main.app.domain.user.auth.session import controller as session_controller
from main.app.domain.user.auth.session.models import AuthSessionDto
from main.appodus_utils.exception.exceptions import UnauthorizedException


def _request_with_refresh(token: str | None):
    # The refresh cookie is issued under the configured key (__Host-refresh_token),
    # not the bare "refresh_token" — the controller must read the configured name.
    cookie_key = settings.AUTHJWT_REFRESH_COOKIE_KEY
    return SimpleNamespace(cookies={cookie_key: token} if token else {})


class TestRefreshRevokedSession:
    async def test_rejects_when_device_session_revoked_or_absent(self, monkeypatch):
        fake_service = MagicMock()
        fake_service.get_device_by_token_hash = AsyncMock(return_value=None)
        monkeypatch.setattr(session_controller, "session_service", fake_service)
        refresh = AsyncMock()
        monkeypatch.setattr(session_controller.JwtAuthUtils, "refresh_access_token", refresh)

        authorize = MagicMock()
        authorize.unset_jwt_cookies = MagicMock()

        with pytest.raises(UnauthorizedException):
            await session_controller.refresh_session(_request_with_refresh("rt"), authorize)

        authorize.unset_jwt_cookies.assert_called_once()
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

    async def test_rejects_when_no_refresh_cookie(self, monkeypatch):
        fake_service = MagicMock()
        fake_service.get_device_by_token_hash = AsyncMock(return_value=None)
        monkeypatch.setattr(session_controller, "session_service", fake_service)
        authorize = MagicMock()
        authorize.unset_jwt_cookies = MagicMock()

        with pytest.raises(UnauthorizedException):
            await session_controller.refresh_session(_request_with_refresh(None), authorize)

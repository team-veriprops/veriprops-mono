"""Unit tests for revoked-session enforcement on token refresh (S6)."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.config.settings import settings
from main.app.domain.user.auth.session import controller as session_controller
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
        fake_service = MagicMock()
        fake_service.get_device_by_token_hash = AsyncMock(return_value=MagicMock(id="dev-1"))
        fake_service.touch_device_session = AsyncMock()
        monkeypatch.setattr(session_controller, "session_service", fake_service)
        refresh = AsyncMock()
        monkeypatch.setattr(session_controller.JwtAuthUtils, "refresh_access_token", refresh)

        authorize = MagicMock()
        resp = await session_controller.refresh_session(_request_with_refresh("rt"), authorize)

        assert resp.data is True
        refresh.assert_awaited_once()
        fake_service.touch_device_session.assert_awaited_once()

    async def test_rejects_when_no_refresh_cookie(self, monkeypatch):
        fake_service = MagicMock()
        fake_service.get_device_by_token_hash = AsyncMock(return_value=None)
        monkeypatch.setattr(session_controller, "session_service", fake_service)
        authorize = MagicMock()
        authorize.unset_jwt_cookies = MagicMock()

        with pytest.raises(UnauthorizedException):
            await session_controller.refresh_session(_request_with_refresh(None), authorize)

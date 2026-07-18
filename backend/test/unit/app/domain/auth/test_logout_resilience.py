"""Unit tests for best-effort logout: cookies must always clear, even when
there is nothing valid to revoke or a revoke write fails."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from main.app.config.settings import settings
from main.app.domain.user.auth.session import controller as session_controller


def _request_with_refresh(token: str | None):
    cookie_key = settings.AUTHJWT_REFRESH_COOKIE_KEY
    return SimpleNamespace(cookies={cookie_key: token} if token else {})


def _make_authorize(jwt_required_error: Exception | None = None):
    authorize = MagicMock()
    authorize.jwt_required = AsyncMock(side_effect=jwt_required_error)
    authorize.unset_jwt_cookies = MagicMock()
    return authorize


class TestLogoutResilience:
    async def test_happy_path_revokes_and_unsets_cookies(self, monkeypatch):
        fake_service = MagicMock()
        fake_service.revoke_current_device = AsyncMock()
        monkeypatch.setattr(session_controller, "session_service", fake_service)
        revoke_token = AsyncMock()
        monkeypatch.setattr(session_controller.JwtAuthUtils, "revoke_token", revoke_token)

        authorize = _make_authorize()
        resp = await session_controller.logout(_request_with_refresh("rt"), authorize)

        fake_service.revoke_current_device.assert_awaited_once_with("rt")
        revoke_token.assert_awaited_once_with(authorize=authorize)
        authorize.unset_jwt_cookies.assert_called_once()
        assert resp.data is True

    async def test_revoke_current_device_failure_still_unsets_cookies(self, monkeypatch):
        fake_service = MagicMock()
        fake_service.revoke_current_device = AsyncMock(side_effect=RuntimeError("db error"))
        monkeypatch.setattr(session_controller, "session_service", fake_service)
        revoke_token = AsyncMock()
        monkeypatch.setattr(session_controller.JwtAuthUtils, "revoke_token", revoke_token)

        authorize = _make_authorize()
        resp = await session_controller.logout(_request_with_refresh("rt"), authorize)

        authorize.unset_jwt_cookies.assert_called_once()
        revoke_token.assert_not_awaited()
        assert resp.data is True

    async def test_jwt_required_failure_still_unsets_cookies(self, monkeypatch):
        fake_service = MagicMock()
        fake_service.revoke_current_device = AsyncMock()
        monkeypatch.setattr(session_controller, "session_service", fake_service)
        revoke_token = AsyncMock()
        monkeypatch.setattr(session_controller.JwtAuthUtils, "revoke_token", revoke_token)

        authorize = _make_authorize(jwt_required_error=RuntimeError("token expired"))
        resp = await session_controller.logout(_request_with_refresh("rt"), authorize)

        authorize.unset_jwt_cookies.assert_called_once()
        fake_service.revoke_current_device.assert_not_awaited()
        revoke_token.assert_not_awaited()
        assert resp.data is True

    async def test_no_refresh_cookie_skips_device_revoke_but_still_revokes_token(self, monkeypatch):
        fake_service = MagicMock()
        fake_service.revoke_current_device = AsyncMock()
        monkeypatch.setattr(session_controller, "session_service", fake_service)
        revoke_token = AsyncMock()
        monkeypatch.setattr(session_controller.JwtAuthUtils, "revoke_token", revoke_token)

        authorize = _make_authorize()
        resp = await session_controller.logout(_request_with_refresh(None), authorize)

        fake_service.revoke_current_device.assert_not_awaited()
        revoke_token.assert_awaited_once_with(authorize=authorize)
        authorize.unset_jwt_cookies.assert_called_once()
        assert resp.data is True

"""Logout always clears the session cookies, and says so when it could not revoke the session.

The cookies are HttpOnly, so logout's response is the client's only way to clear them — on
success and failure alike. A refresh cookie always names a device session to end, even once the
access token has lapsed; with neither token present logout simply succeeds. When the revocation itself fails (the device row or the denylist write),
the response is the standard safe 5xx with a reference instead of a false success, and the
cookie deletions are attached to that response rather than lost with a raised exception.
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from libre_fastapi_jwt.exceptions import MissingTokenError
from starlette.responses import JSONResponse

from main.app.config.settings import settings
from main.app.domain.user.auth.session import controller as session_controller
from main.appodus_utils.exception.exception_handlers import SERVER_ERROR_MESSAGE


def _request_with_refresh(token: str | None):
    cookie_key = settings.AUTHJWT_REFRESH_COOKIE_KEY
    return SimpleNamespace(cookies={cookie_key: token} if token else {}, state=SimpleNamespace())


def _make_authorize(jwt_required_error: Exception | None = None):
    authorize = MagicMock()
    authorize.jwt_required = AsyncMock(side_effect=jwt_required_error)
    authorize.unset_jwt_cookies = MagicMock()
    return authorize


def _wire(monkeypatch, *, device_error=None, token_error=None):
    fake_service = MagicMock()
    fake_service.revoke_current_device = AsyncMock(side_effect=device_error)
    monkeypatch.setattr(session_controller, "session_service", fake_service)
    revoke_token = AsyncMock(side_effect=token_error)
    monkeypatch.setattr(session_controller.JwtAuthUtils, "revoke_token", revoke_token)
    return fake_service, revoke_token


def _assert_failed_with_cookies_cleared(resp, authorize):
    assert isinstance(resp, JSONResponse)
    assert resp.status_code == 500
    body = json.loads(resp.body)
    assert body["error"]["message"] == SERVER_ERROR_MESSAGE
    assert body["error"]["reference"]
    # Cleared on the response actually returned, so the browser drops the cookies.
    authorize.unset_jwt_cookies.assert_called_once_with(resp)


class TestLogoutResilience:
    async def test_happy_path_revokes_and_unsets_cookies(self, monkeypatch):
        fake_service, revoke_token = _wire(monkeypatch)

        authorize = _make_authorize()
        resp = await session_controller.logout(_request_with_refresh("rt"), authorize)

        fake_service.revoke_current_device.assert_awaited_once_with("rt")
        revoke_token.assert_awaited_once_with(authorize=authorize)
        authorize.unset_jwt_cookies.assert_called_once()
        assert resp.data is True

    async def test_a_failed_device_revocation_is_reported_and_cookies_still_clear(self, monkeypatch):
        _, revoke_token = _wire(monkeypatch, device_error=RuntimeError("db error"))

        authorize = _make_authorize()
        resp = await session_controller.logout(_request_with_refresh("rt"), authorize)

        revoke_token.assert_not_awaited()
        _assert_failed_with_cookies_cleared(resp, authorize)

    async def test_a_failed_denylist_write_is_reported_and_cookies_still_clear(self, monkeypatch):
        _wire(monkeypatch, token_error=ConnectionError("store down"))

        authorize = _make_authorize()
        resp = await session_controller.logout(_request_with_refresh("rt"), authorize)

        _assert_failed_with_cookies_cleared(resp, authorize)

    async def test_nothing_valid_to_revoke_is_a_plain_sign_out(self, monkeypatch):
        fake_service, revoke_token = _wire(monkeypatch)

        authorize = _make_authorize(jwt_required_error=MissingTokenError(401, "Missing token"))
        resp = await session_controller.logout(_request_with_refresh(None), authorize)

        authorize.unset_jwt_cookies.assert_called_once()
        fake_service.revoke_current_device.assert_not_awaited()
        revoke_token.assert_not_awaited()
        assert resp.data is True

    async def test_an_expired_access_token_still_revokes_the_device_its_refresh_cookie_names(
        self, monkeypatch
    ):
        # A sign-out retried after the access token lapsed (the queued logout a failsafe
        # redirect leaves behind) must still end the session: the refresh token outlives the
        # access token, and clearing this browser's cookies alone leaves it usable elsewhere.
        fake_service, revoke_token = _wire(monkeypatch)

        authorize = _make_authorize(jwt_required_error=MissingTokenError(401, "Missing token"))
        resp = await session_controller.logout(_request_with_refresh("rt"), authorize)

        fake_service.revoke_current_device.assert_awaited_once_with("rt")
        # There is no verified access token to denylist.
        revoke_token.assert_not_awaited()
        authorize.unset_jwt_cookies.assert_called_once()
        assert resp.data is True

    async def test_a_failed_device_revocation_after_an_expired_access_token_is_reported(
        self, monkeypatch
    ):
        _wire(monkeypatch, device_error=RuntimeError("db error"))

        authorize = _make_authorize(jwt_required_error=MissingTokenError(401, "Missing token"))
        resp = await session_controller.logout(_request_with_refresh("rt"), authorize)

        _assert_failed_with_cookies_cleared(resp, authorize)

    async def test_a_store_outage_during_the_token_check_is_reported(self, monkeypatch):
        fake_service, _ = _wire(monkeypatch)

        # The denylist read fails closed, so the token check itself raises a non-JWT error.
        authorize = _make_authorize(jwt_required_error=ConnectionError("store down"))
        resp = await session_controller.logout(_request_with_refresh("rt"), authorize)

        fake_service.revoke_current_device.assert_not_awaited()
        _assert_failed_with_cookies_cleared(resp, authorize)

    async def test_no_refresh_cookie_skips_device_revoke_but_still_revokes_token(self, monkeypatch):
        fake_service, revoke_token = _wire(monkeypatch)

        authorize = _make_authorize()
        resp = await session_controller.logout(_request_with_refresh(None), authorize)

        fake_service.revoke_current_device.assert_not_awaited()
        revoke_token.assert_awaited_once_with(authorize=authorize)
        authorize.unset_jwt_cookies.assert_called_once()
        assert resp.data is True

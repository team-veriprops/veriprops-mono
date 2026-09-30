"""Setting or changing a password from the account page (§1.3).

An account that signed up through a social provider has no password and may set a first one
from its session. Changing an existing password needs the current one — a session alone
(say, a stolen cookie) must not be able to lock the owner out — and a wrong one is refused
and recorded where the owner will see it. Every change signs out every other session and
keeps this one, the same way a reset link signs out everything.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from main.app.domain.user.auth.service import AuthService
from main.app.domain.user.auth.session.models import SecurityEventType
from main.appodus_utils import Utils
from main.appodus_utils.exception.exceptions import ValidationException
from test.utils.db_session import mock_db_session  # noqa: F401  (autouse fixture)

_NEW = "N3w-Passw0rd!"
_CURRENT = "Old-Passw0rd!"


def _service(password_hash=None):
    svc = object.__new__(AuthService)
    svc._user_service = AsyncMock()
    svc._user_service.get_user_model = AsyncMock(return_value=SimpleNamespace(id="u1", password_hash=password_hash))
    svc._session_service = AsyncMock()
    svc._failures = AsyncMock()
    return svc


def _events(svc):
    return [c.args[0] for c in svc._session_service.record_event.await_args_list]


class TestFirstPassword:
    async def test_an_account_without_a_password_sets_one_from_its_session(self):
        svc = _service(password_hash=None)

        await svc.set_password("u1", _NEW, current_password=None, keep_session_hash="this-device")

        new_hash = svc._user_service.set_password_hash.await_args.args[1]
        assert Utils.verify_password(_NEW, new_hash)
        assert _events(svc) == [SecurityEventType.PASSWORD_CHANGED]

    async def test_setting_one_signs_out_every_other_session_and_keeps_this_one(self):
        svc = _service(password_hash=None)

        await svc.set_password("u1", _NEW, current_password=None, keep_session_hash="this-device")

        svc._session_service.revoke_all_other_devices.assert_awaited_once_with("u1", "this-device")


class TestChangingAPassword:
    async def test_needs_the_current_password(self):
        svc = _service(password_hash=Utils.get_password_hash(_CURRENT))

        with pytest.raises(ValidationException, match="current password"):
            await svc.set_password("u1", _NEW, current_password=None, keep_session_hash="this-device")

        svc._user_service.set_password_hash.assert_not_awaited()
        svc._session_service.revoke_all_other_devices.assert_not_awaited()

    async def test_a_wrong_current_password_is_refused_and_recorded(self):
        svc = _service(password_hash=Utils.get_password_hash(_CURRENT))

        with pytest.raises(ValidationException, match="current password"):
            await svc.set_password("u1", _NEW, current_password="not-it", keep_session_hash="this-device")

        svc._user_service.set_password_hash.assert_not_awaited()
        svc._session_service.revoke_all_other_devices.assert_not_awaited()
        # Recorded on its own commit: the refusal's rollback must not erase it.
        assert svc._failures.record_event.await_args.args[0] == SecurityEventType.PASSWORD_CHANGE_REFUSED
        assert svc._failures.record_event.await_args.kwargs["user_id"] == "u1"
        assert _events(svc) == []

    async def test_the_right_current_password_changes_it_and_signs_out_other_sessions(self):
        svc = _service(password_hash=Utils.get_password_hash(_CURRENT))

        await svc.set_password("u1", _NEW, current_password=_CURRENT, keep_session_hash="this-device")

        assert Utils.verify_password(_NEW, svc._user_service.set_password_hash.await_args.args[1])
        svc._session_service.revoke_all_other_devices.assert_awaited_once_with("u1", "this-device")
        assert _events(svc) == [SecurityEventType.PASSWORD_CHANGED]

    async def test_a_weak_new_password_is_refused_before_anything_is_checked(self):
        svc = _service(password_hash=Utils.get_password_hash(_CURRENT))

        with pytest.raises(ValidationException):
            await svc.set_password("u1", "short", current_password=_CURRENT, keep_session_hash="this-device")

        svc._user_service.set_password_hash.assert_not_awaited()

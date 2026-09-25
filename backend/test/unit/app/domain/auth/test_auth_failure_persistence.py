"""What a failed sign-in leaves behind survives the failure.

`SessionService.login` records a failed attempt (the counter, the lock, the security events)
and then raises. Those writes used to share the login transaction, so the raise rolled them
back: the counter never grew, the account never locked, and the security log never showed
the attempt. They now go through `AuthFailureRecorder`, which commits on its own
(`INDEPENDENT`). The counter is also one atomic `UPDATE … RETURNING`, so concurrent wrong
passwords each count.
"""
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from kink import di
from sqlalchemy.dialects import postgresql

from main.app.config.settings import settings
from main.app.domain.user.auth.session.failure_recorder import AuthFailureRecorder
from main.app.domain.user.auth.session.models import LoginRequestDto, SecurityEventType
from main.app.domain.user.auth.session.service import SessionService
from main.app.domain.user.models import AccountStatus
from main.app.domain.user.repo import UserRepo
from main.app.domain.user.service import UserService
from main.appodus_utils import Utils
from main.appodus_utils.db.session import db_session_ctx, is_independent_session
from main.appodus_utils.exception.exceptions import InvalidCredentialsException, UnauthorizedException

_PASSWORD = "Str0ng-Passw0rd!"


@pytest.fixture(autouse=True)
def request_session():
    session = MagicMock()
    session.in_transaction.return_value = False

    @asynccontextmanager
    async def _begin():
        yield

    session.begin = _begin
    session.flush = AsyncMock()
    token = db_session_ctx.set(session)
    yield session
    db_session_ctx.reset(token)


def _recorder():
    rec = object.__new__(AuthFailureRecorder)
    rec._user_repo = MagicMock(increment_failed_login=AsyncMock(), lock_until=AsyncMock())
    rec._event_repo = MagicMock(create=AsyncMock())
    return rec


def _event_types(rec) -> list:
    return [c.args[0].type for c in rec._event_repo.create.await_args_list]


# ── The recorder ───────────────────────────────────────────────────────


async def test_the_recorder_writes_in_its_own_transaction(independent_sessions):
    rec = _recorder()
    sessions_seen = []
    rec._user_repo.increment_failed_login = AsyncMock(
        side_effect=lambda _uid: sessions_seen.append(db_session_ctx.get()) or 1
    )

    await rec.record_failed_login("u1")

    assert len(independent_sessions) == 1
    assert is_independent_session(sessions_seen[0])


async def test_below_the_warning_mark_it_logs_a_plain_failure(independent_sessions):
    rec = _recorder()
    rec._user_repo.increment_failed_login.return_value = 1

    assert await rec.record_failed_login("u1") == 1

    rec._user_repo.lock_until.assert_not_awaited()
    assert _event_types(rec) == [SecurityEventType.LOGIN_FAILURE]


async def test_near_the_threshold_it_warns(independent_sessions):
    rec = _recorder()
    rec._user_repo.increment_failed_login.return_value = settings.AUTH_LOCKOUT_THRESHOLD - 1

    await rec.record_failed_login("u1")

    rec._user_repo.lock_until.assert_not_awaited()
    assert _event_types(rec) == [SecurityEventType.LOGIN_FAILURE_WARNING]


async def test_at_the_threshold_it_locks_the_account(independent_sessions):
    rec = _recorder()
    rec._user_repo.increment_failed_login.return_value = settings.AUTH_LOCKOUT_THRESHOLD

    await rec.record_failed_login("u1")

    user_id, until = rec._user_repo.lock_until.await_args.args
    assert user_id == "u1" and until > Utils.datetime_now()
    assert _event_types(rec) == [SecurityEventType.ACCOUNT_LOCKED]


# ── Login routes every failure through the recorder ─────────────────────


def _user(**over):
    base = dict(
        id=uuid.uuid4(), password_hash=Utils.get_password_hash(_PASSWORD), locked_until=None,
        failed_login_count=0, account_status=AccountStatus.ACTIVE.value, user_type="USER",
        personas=["CUSTOMER"], admin_sub_role=None,
    )
    base.update(over)
    return SimpleNamespace(**base)


@pytest.fixture
def login_with():
    original = di[UserService]

    def _make(user):
        user_service = MagicMock(
            get_user_by_email=AsyncMock(return_value=user),
            reset_failed_login=AsyncMock(),
        )
        di[UserService] = user_service
        svc = object.__new__(SessionService)
        svc._device_repo = AsyncMock()
        svc._event_repo = AsyncMock()
        svc._reset_repo = AsyncMock()
        svc._failures = MagicMock(record_failed_login=AsyncMock(return_value=1), record_event=AsyncMock())
        return svc, user_service

    yield _make
    di[UserService] = original


async def test_a_wrong_password_is_recorded_by_the_recorder(login_with):
    user = _user()
    svc, _ = login_with(user)

    with pytest.raises(InvalidCredentialsException):
        await svc.login(LoginRequestDto(email="a@example.com", password="wrong-password-1"))

    svc._failures.record_failed_login.assert_awaited_once()
    assert svc._failures.record_failed_login.await_args.args == (str(user.id),)
    svc._event_repo.create.assert_not_awaited()  # nothing rides the doomed transaction


async def test_an_unknown_email_is_recorded_by_the_recorder(login_with):
    svc, _ = login_with(None)

    with pytest.raises(InvalidCredentialsException):
        await svc.login(LoginRequestDto(email="nobody@example.com", password="whatever-pass-1"))

    assert svc._failures.record_event.await_args.args[0] == SecurityEventType.LOGIN_FAILURE
    svc._event_repo.create.assert_not_awaited()


async def test_a_locked_account_attempt_is_recorded_by_the_recorder(login_with):
    locked = _user(locked_until=datetime(2999, 1, 1, tzinfo=timezone.utc))
    svc, _ = login_with(locked)

    with pytest.raises(UnauthorizedException):
        await svc.login(LoginRequestDto(email="a@example.com", password=_PASSWORD))

    assert svc._failures.record_event.await_args.args[0] == SecurityEventType.LOGIN_FAILURE
    svc._failures.record_failed_login.assert_not_awaited()


async def test_a_suspended_account_attempt_is_recorded_by_the_recorder(login_with):
    svc, _ = login_with(_user(account_status=AccountStatus.SUSPENDED.value))

    with pytest.raises(UnauthorizedException):
        await svc.login(LoginRequestDto(email="a@example.com", password=_PASSWORD))

    assert svc._failures.record_event.await_args.args[0] == SecurityEventType.LOGIN_FAILURE


# ── The user row's counters are single statements ───────────────────────


@pytest.fixture
def captured_user_sql(request_session):
    statements = []

    async def _execute(stmt):
        statements.append(stmt)
        result = MagicMock()
        result.scalar_one.return_value = 3
        return result

    request_session.execute = AsyncMock(side_effect=_execute)
    return statements


def _sql(stmt) -> str:
    return " ".join(str(stmt.compile(dialect=postgresql.dialect())).split())


def _user_repo() -> UserRepo:
    return object.__new__(UserRepo)


async def test_the_failed_login_counter_increments_in_sql(captured_user_sql):
    count = await _user_repo().increment_failed_login(str(uuid.uuid4()))

    assert count == 3
    sql = _sql(captured_user_sql[0])
    assert "SET failed_login_count=(coalesce(users.failed_login_count, %(coalesce_1)s) + %(coalesce_2)s)" in sql
    assert sql.endswith("RETURNING users.failed_login_count")


async def test_a_successful_login_really_clears_the_lock(captured_user_sql):
    await _user_repo().reset_failed_login(str(uuid.uuid4()))

    compiled = captured_user_sql[0].compile(dialect=postgresql.dialect())
    assert "locked_until=%(locked_until)s" in " ".join(str(compiled).split())
    assert compiled.params["locked_until"] is None and compiled.params["failed_login_count"] == 0

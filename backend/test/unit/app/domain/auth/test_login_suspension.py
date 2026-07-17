"""Suspended accounts must not authenticate (PRD §2.4a).

Covers both session-issuance paths: password login (`SessionService.login`) and the
common choke point `issue_session_cookies` (which also guards OAuth logins).
"""
import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from kink import di

from main.app.domain.user.auth.session.models import LoginRequestDto
from main.app.domain.user.auth.session.service import SessionService
from main.app.domain.user.models import AccountStatus
from main.app.domain.user.service import UserService
from main.appodus_utils import Utils
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.exception.exceptions import UnauthorizedException


@pytest.fixture(autouse=True)
def mock_db_session():
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


def _make_session_service():
    svc = object.__new__(SessionService)
    svc._device_repo = AsyncMock()
    svc._event_repo = AsyncMock()
    svc._reset_repo = AsyncMock()
    return svc


def _suspended_user(password: str):
    return SimpleNamespace(
        id=uuid.uuid4(),
        password_hash=Utils.get_password_hash(password),
        locked_until=None,
        failed_login_count=0,
        account_status=AccountStatus.SUSPENDED.value,
        user_type="USER",
        personas=["CUSTOMER"],
        admin_sub_role=None,
    )


async def test_login_rejects_suspended_account_with_valid_credentials():
    password = "Str0ng-Passw0rd!"
    user = _suspended_user(password)

    user_service = MagicMock()
    user_service.get_user_by_email = AsyncMock(return_value=user)
    original = di[UserService]
    di[UserService] = user_service
    try:
        svc = _make_session_service()
        with pytest.raises(UnauthorizedException):
            await svc.login(LoginRequestDto(email="s@example.com", password=password))
        # The rejection is recorded in the user's security activity log.
        svc._event_repo.create.assert_awaited()
    finally:
        di[UserService] = original


async def test_issue_session_cookies_rejects_suspended_account():
    user = _suspended_user("irrelevant")
    svc = _make_session_service()
    with pytest.raises(UnauthorizedException):
        await svc.issue_session_cookies(user, authorize=MagicMock())
    svc._device_repo.create.assert_not_awaited()

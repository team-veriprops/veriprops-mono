"""AdminInvitationService (PRD §4.1, decision-log D10) — repos mocked, no DB."""
from contextlib import asynccontextmanager
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.domain.audit.models import AuditActionType
from main.app.domain.user.admin_invitation.models import (
    AdminInvitationStatus,
    InviteAcceptScenario,
)
from main.app.domain.user.admin_invitation.service import AdminInvitationService
from main.app.domain.user.auth.session.models import UserType
from main.app.domain.user.models import AdminSubRole
from main.appodus_utils import Utils
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.exception.exceptions import (
    ForbiddenException,
    InvalidTokenException,
)


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


def _make_service():
    svc = object.__new__(AdminInvitationService)
    svc._repo = MagicMock()
    svc._user_service = MagicMock()
    svc._audit_service = MagicMock()
    svc._repo.create_return_model = AsyncMock(return_value=SimpleNamespace(id="inv-1"))
    svc._repo.update = AsyncMock()
    svc._repo.get_model = AsyncMock(return_value=SimpleNamespace(id="inv-1", accepted_at=None))
    return svc


def _invitation(**over):
    base = dict(
        id="inv-1",
        email="new@example.com",
        email_normalized="new@example.com",
        sub_role=AdminSubRole.OPERATIONS.value,
        status=AdminInvitationStatus.PENDING.value,
        expires_at=Utils.datetime_now() + timedelta(hours=1),
    )
    base.update(over)
    return SimpleNamespace(**base)


class TestInvite:
    async def test_creates_and_audits(self):
        svc = _make_service()
        raw = await svc.invite("new@example.com", AdminSubRole.OPERATIONS, invited_by="super-1")
        assert isinstance(raw, str) and len(raw) >= 20
        svc._repo.create_return_model.assert_awaited_once()
        assert svc._audit_service.schedule.call_args.kwargs["action"] == AuditActionType.ADMIN_INVITED


class TestPreview:
    async def test_new_user_scenario(self):
        svc = _make_service()
        svc._repo.get_by_token_hash = AsyncMock(return_value=_invitation())
        svc._user_service.get_user_by_email = AsyncMock(return_value=None)
        preview = await svc.preview("raw")
        assert preview.scenario == InviteAcceptScenario.NEW_USER
        assert preview.expired is False

    async def test_existing_user_scenario(self):
        svc = _make_service()
        svc._repo.get_by_token_hash = AsyncMock(return_value=_invitation())
        svc._user_service.get_user_by_email = AsyncMock(
            return_value=SimpleNamespace(user_type=UserType.USER.value)
        )
        assert (await svc.preview("raw")).scenario == InviteAcceptScenario.EXISTING_USER

    async def test_already_admin_scenario(self):
        svc = _make_service()
        svc._repo.get_by_token_hash = AsyncMock(return_value=_invitation())
        svc._user_service.get_user_by_email = AsyncMock(
            return_value=SimpleNamespace(user_type=UserType.ADMIN.value)
        )
        assert (await svc.preview("raw")).scenario == InviteAcceptScenario.ALREADY_ADMIN


class TestAccept:
    async def test_elevates_matching_user_to_admin(self):
        svc = _make_service()
        svc._repo.get_by_token_hash = AsyncMock(return_value=_invitation())
        svc._user_service.get_user_model = AsyncMock(
            return_value=SimpleNamespace(email="new@example.com", user_type=UserType.USER.value)
        )
        svc._user_service.update_user = AsyncMock()

        sub_role = await svc.accept("raw", current_user_id="u-1")
        assert sub_role == AdminSubRole.OPERATIONS
        # Elevation: user_type -> ADMIN with the invited sub-role.
        update_dto = svc._user_service.update_user.call_args.args[1]
        assert update_dto.user_type == UserType.ADMIN.value
        assert update_dto.admin_sub_role == AdminSubRole.OPERATIONS.value
        assert svc._audit_service.schedule.call_args.kwargs["action"] == AuditActionType.ADMIN_INVITE_ACCEPTED

    async def test_rejects_email_mismatch(self):
        svc = _make_service()
        svc._repo.get_by_token_hash = AsyncMock(return_value=_invitation())
        svc._user_service.get_user_model = AsyncMock(
            return_value=SimpleNamespace(email="someone.else@example.com", user_type=UserType.USER.value)
        )
        with pytest.raises(ForbiddenException):
            await svc.accept("raw", current_user_id="u-1")

    async def test_rejects_expired_token(self):
        svc = _make_service()
        svc._repo.get_by_token_hash = AsyncMock(
            return_value=_invitation(expires_at=Utils.datetime_now() - timedelta(hours=1))
        )
        svc._user_service.get_user_model = AsyncMock(
            return_value=SimpleNamespace(email="new@example.com", user_type=UserType.USER.value)
        )
        with pytest.raises(InvalidTokenException):
            await svc.accept("raw", current_user_id="u-1")

    async def test_rejects_already_accepted_token(self):
        svc = _make_service()
        svc._repo.get_by_token_hash = AsyncMock(
            return_value=_invitation(status=AdminInvitationStatus.ACCEPTED.value)
        )
        svc._user_service.get_user_model = AsyncMock(
            return_value=SimpleNamespace(email="new@example.com", user_type=UserType.USER.value)
        )
        with pytest.raises(InvalidTokenException):
            await svc.accept("raw", current_user_id="u-1")

    async def test_rejects_invalid_token(self):
        svc = _make_service()
        svc._repo.get_by_token_hash = AsyncMock(return_value=None)
        with pytest.raises(InvalidTokenException):
            await svc.accept("bad", current_user_id="u-1")

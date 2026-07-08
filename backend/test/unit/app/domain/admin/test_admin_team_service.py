"""AdminTeamService (PRD §4.1) — repos mocked, no DB."""
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.domain.audit.models import AuditActionType
from main.app.domain.user.admin_team.service import AdminTeamService
from main.app.domain.user.auth.session.models import UserType
from main.app.domain.user.models import AdminSubRole
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.exception.exceptions import ResourceNotFoundException, ValidationException


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


def _make_service(target_user=None, actor_user=None, users=None):
    """Build an AdminTeamService with mocked deps.

    ``get_user_model`` resolves per-id: an explicit ``users`` map wins; otherwise
    ``actor_user`` (defaulting to a SUPER admin, since the endpoint is INVITE_ADMIN-gated)
    is returned for ``admin_id`` and ``target_user`` for everything else.
    """
    if actor_user is None:
        actor_user = _admin(admin_sub_role=AdminSubRole.SUPER.value)

    svc = object.__new__(AdminTeamService)
    svc._user_repo = MagicMock()
    svc._user_service = MagicMock()
    svc._audit_service = MagicMock()
    svc._user_repo.update = AsyncMock()
    svc._user_repo.demote_to_user = AsyncMock()

    async def _get_user_model(user_id):
        if users is not None:
            return users.get(user_id)
        if user_id in ("super-1", "actor-1"):
            return actor_user
        return target_user

    svc._user_service.get_user_model = AsyncMock(side_effect=_get_user_model)
    return svc


def _admin(**over):
    base = dict(user_type=UserType.ADMIN.value, admin_sub_role=AdminSubRole.OPERATIONS.value)
    base.update(over)
    return SimpleNamespace(**base)


class TestListTeam:
    async def test_forwards_search_and_sub_role_filter(self):
        svc = _make_service()
        svc._user_repo.list_admins = AsyncMock(return_value=[])
        await svc.list_team(page=0, page_size=10, query="ada", sub_role=AdminSubRole.FINANCE.value)
        svc._user_repo.list_admins.assert_awaited_once_with(
            sub_role_filter=AdminSubRole.FINANCE, query="ada"
        )

    async def test_builds_dto_from_real_uuid_id(self):
        """Real entity ids are ``uuid.UUID``; the member DTO must expose them as hex strings."""
        admin_id = uuid.uuid4()
        admin = _admin(
            id=admin_id, first_name="Ada", last_name="Lovelace",
            email="ada@veriprops.io", deleted=False,
            date_created=datetime(2026, 7, 5, tzinfo=timezone.utc),
        )
        svc = _make_service()
        svc._user_repo.list_admins = AsyncMock(return_value=[admin])
        page = await svc.list_team(page=0, page_size=10)
        assert page.items[0].id == admin_id.hex
        assert page.items[0].sub_role == AdminSubRole.OPERATIONS


class TestChangeSubRole:
    async def test_updates_and_audits(self):
        svc = _make_service(target_user=_admin())
        await svc.change_sub_role("u-2", AdminSubRole.FINANCE, admin_id="super-1")
        svc._user_repo.update.assert_awaited_once()
        kwargs = svc._audit_service.schedule.call_args.kwargs
        assert kwargs["action"] == AuditActionType.ADMIN_ROLE_CHANGED
        assert kwargs["to_state"] == AdminSubRole.FINANCE.value

    async def test_rejects_non_admin_target(self):
        svc = _make_service(
            actor_user=_admin(admin_sub_role=AdminSubRole.SUPER.value),
            target_user=_admin(user_type=UserType.USER.value),
        )
        with pytest.raises(ResourceNotFoundException):
            await svc.change_sub_role("u-2", AdminSubRole.FINANCE, admin_id="super-1")

    async def test_cannot_change_own_sub_role(self):
        """An admin must not change their own sub-role (mirrors deactivate's self-guard)."""
        actor = _admin(admin_sub_role=AdminSubRole.SUPER.value)
        svc = _make_service(users={"super-1": actor})
        with pytest.raises(ValidationException):
            await svc.change_sub_role("super-1", AdminSubRole.OPERATIONS, admin_id="super-1")
        svc._user_repo.update.assert_not_awaited()

    async def test_non_super_cannot_grant_super(self):
        """Even reaching the service, a non-SUPER actor cannot mint a SUPER admin."""
        svc = _make_service(
            users={
                "actor-1": _admin(admin_sub_role=AdminSubRole.OPERATIONS.value),
                "u-2": _admin(admin_sub_role=AdminSubRole.OPERATIONS.value),
            }
        )
        with pytest.raises(ValidationException):
            await svc.change_sub_role("u-2", AdminSubRole.SUPER, admin_id="actor-1")
        svc._user_repo.update.assert_not_awaited()

    async def test_super_can_grant_super(self):
        svc = _make_service(
            users={
                "super-1": _admin(admin_sub_role=AdminSubRole.SUPER.value),
                "u-2": _admin(admin_sub_role=AdminSubRole.OPERATIONS.value),
            }
        )
        await svc.change_sub_role("u-2", AdminSubRole.SUPER, admin_id="super-1")
        svc._user_repo.update.assert_awaited_once()


class TestDeactivate:
    async def test_demotes_and_audits(self):
        svc = _make_service(target_user=_admin())
        await svc.deactivate("u-2", admin_id="super-1")
        svc._user_repo.demote_to_user.assert_awaited_once_with("u-2")
        assert svc._audit_service.schedule.call_args.kwargs["to_state"] == "DEACTIVATED"

    async def test_cannot_deactivate_self(self):
        svc = _make_service(target_user=_admin())
        with pytest.raises(ValidationException):
            await svc.deactivate("super-1", admin_id="super-1")

"""Unit tests for AdminTeamService (R4.5).

Verifies:
- list_admins() returns only ADMIN-type users, optionally filtered by sub_role.
- deactivate_admin() demotes user, clears sub_role, and logs ADMIN_DEACTIVATED.
- deactivate_admin() blocks self-deactivation.
- deactivate_admin() blocks removal of the last SUPER admin.
- deactivate_admin() raises if target is not an admin.
- change_sub_role() updates admin_sub_role and logs ADMIN_ROLE_CHANGED.
- change_sub_role() raises if target is not an admin.
"""
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, call

import pytest

from main.appodus_utils.db.session import db_session_ctx
from main.app.domain.user.auth.session.models import SecurityEventType, UserType
from main.app.domain.user.models import AdminSubRole
from main.appodus_utils.exception.exceptions import (
    InvalidResourceStateException,
    ResourceNotFoundException,
    ValidationException,
)


# ── fixtures ──────────────────────────────────────────────────────────────────

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
    from main.app.domain.user.admin_team.service import AdminTeamService
    svc = object.__new__(AdminTeamService)
    svc._user_repo = AsyncMock()
    svc._session_service = AsyncMock()
    return svc


def _make_admin(
    *,
    user_id: str = "admin-001",
    email: str = "admin@example.com",
    first_name: str = "Alice",
    last_name: str = "Smith",
    sub_role: str = AdminSubRole.OPERATIONS.value,
    user_type: str = UserType.ADMIN.value,
):
    user = MagicMock()
    user.id = user_id
    user.email = email
    user.first_name = first_name
    user.last_name = last_name
    user.admin_sub_role = sub_role
    user.user_type = user_type
    user.date_created = datetime(2026, 5, 7, tzinfo=timezone.utc)
    return user


# ── list_admins ───────────────────────────────────────────────────────────────

async def test_list_admins_returns_all_admins():
    svc = _make_service()
    admins = [
        _make_admin(user_id="a1", sub_role=AdminSubRole.SUPER.value),
        _make_admin(user_id="a2", sub_role=AdminSubRole.OPERATIONS.value),
    ]
    svc._user_repo.list_admins.return_value = admins

    result = await svc.list_admins()

    svc._user_repo.list_admins.assert_called_once_with(sub_role_filter=None)
    assert len(result) == 2
    assert result[0].id == "a1"
    assert result[1].id == "a2"


async def test_list_admins_passes_sub_role_filter():
    svc = _make_service()
    finance_admin = _make_admin(user_id="f1", sub_role=AdminSubRole.FINANCE.value)
    svc._user_repo.list_admins.return_value = [finance_admin]

    result = await svc.list_admins(sub_role_filter=AdminSubRole.FINANCE)

    svc._user_repo.list_admins.assert_called_once_with(sub_role_filter=AdminSubRole.FINANCE)
    assert len(result) == 1
    assert result[0].sub_role == AdminSubRole.FINANCE


async def test_list_admins_empty():
    svc = _make_service()
    svc._user_repo.list_admins.return_value = []

    result = await svc.list_admins()

    assert result == []


# ── deactivate_admin ──────────────────────────────────────────────────────────

async def test_deactivate_admin_demotes_and_logs_event():
    svc = _make_service()
    target = _make_admin(user_id="target-1", sub_role=AdminSubRole.OPERATIONS.value)
    svc._user_repo.get_model.return_value = target

    await svc.deactivate_admin(actor_id="super-1", target_id="target-1")

    svc._user_repo.demote_to_user.assert_called_once_with("target-1")
    svc._session_service.record_event.assert_called_once()
    evt = svc._session_service.record_event.call_args
    assert evt.kwargs["type"] == SecurityEventType.ADMIN_DEACTIVATED
    assert "target-1" in evt.kwargs["description"]


async def test_deactivate_admin_raises_on_self_deactivation():
    svc = _make_service()

    with pytest.raises(ValidationException):
        await svc.deactivate_admin(actor_id="admin-1", target_id="admin-1")

    svc._user_repo.get_model.assert_not_called()


async def test_deactivate_admin_raises_if_target_not_found():
    svc = _make_service()
    svc._user_repo.get_model.return_value = None

    with pytest.raises(ResourceNotFoundException):
        await svc.deactivate_admin(actor_id="super-1", target_id="ghost-1")


async def test_deactivate_admin_raises_if_target_is_not_admin():
    svc = _make_service()
    regular_user = _make_admin(user_id="u1", user_type=UserType.USER.value)
    svc._user_repo.get_model.return_value = regular_user

    with pytest.raises(ResourceNotFoundException):
        await svc.deactivate_admin(actor_id="super-1", target_id="u1")


async def test_deactivate_admin_raises_if_last_super():
    svc = _make_service()
    lone_super = _make_admin(user_id="super-1", sub_role=AdminSubRole.SUPER.value)
    svc._user_repo.get_model.return_value = lone_super
    svc._user_repo.list_admins.return_value = [lone_super]

    with pytest.raises(InvalidResourceStateException):
        await svc.deactivate_admin(actor_id="other-1", target_id="super-1")

    svc._user_repo.demote_to_user.assert_not_called()


async def test_deactivate_super_admin_allowed_when_another_super_exists():
    svc = _make_service()
    target_super = _make_admin(user_id="super-1", sub_role=AdminSubRole.SUPER.value)
    other_super = _make_admin(user_id="super-2", sub_role=AdminSubRole.SUPER.value)
    svc._user_repo.get_model.return_value = target_super
    svc._user_repo.list_admins.return_value = [target_super, other_super]

    await svc.deactivate_admin(actor_id="super-2", target_id="super-1")

    svc._user_repo.demote_to_user.assert_called_once_with("super-1")


# ── change_sub_role ───────────────────────────────────────────────────────────

async def test_change_sub_role_updates_and_logs_event():
    svc = _make_service()
    target = _make_admin(user_id="admin-1", sub_role=AdminSubRole.OPERATIONS.value)
    updated = _make_admin(user_id="admin-1", sub_role=AdminSubRole.FINANCE.value)
    svc._user_repo.get_model.side_effect = [target, updated]

    result = await svc.change_sub_role(
        actor_id="super-1",
        target_id="admin-1",
        new_sub_role=AdminSubRole.FINANCE,
    )

    svc._user_repo.update.assert_called_once()
    svc._session_service.record_event.assert_called_once()
    evt = svc._session_service.record_event.call_args
    assert evt.kwargs["type"] == SecurityEventType.ADMIN_ROLE_CHANGED
    assert "OPERATIONS" in evt.kwargs["description"]
    assert "FINANCE" in evt.kwargs["description"]
    assert result.sub_role == AdminSubRole.FINANCE


async def test_change_sub_role_raises_if_target_not_found():
    svc = _make_service()
    svc._user_repo.get_model.return_value = None

    with pytest.raises(ResourceNotFoundException):
        await svc.change_sub_role(
            actor_id="super-1",
            target_id="ghost-1",
            new_sub_role=AdminSubRole.FINANCE,
        )


async def test_change_sub_role_raises_if_target_not_admin():
    svc = _make_service()
    regular_user = _make_admin(user_id="u1", user_type=UserType.USER.value)
    svc._user_repo.get_model.return_value = regular_user

    with pytest.raises(ResourceNotFoundException):
        await svc.change_sub_role(
            actor_id="super-1",
            target_id="u1",
            new_sub_role=AdminSubRole.OPERATIONS,
        )

"""Unit tests for AdminInvitationService (R4.1, R4.2, R4.3, R4.6).

Verifies:
- R4.1  invite() creates tokenised invitation + records ADMIN_INVITED event.
- R4.2  Expired tokens are rejected (72-hr TTL enforced).
- R4.3  Three acceptance branches: SIGNUP_REQUIRED / LOGIN_REQUIRED / ALREADY_ADMIN / ACCEPTED.
- R4.6  attach_admin_role_to_new_user() wires the invite into the signup flow.
"""
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, call

import pytest

from main.appodus_utils.db.session import db_session_ctx
from main.app.domain.user.admin_invitation.models import (
    AdminInvitationStatus,
    AdminSubRole,
)
from main.app.domain.user.auth.session.models import SecurityEventType, UserType
from main.appodus_utils.exception.exceptions import (
    InvalidResourceStateException,
    ResourceNotFoundException,
    ValidationException,
)

_FUTURE = datetime(2099, 12, 31, tzinfo=timezone.utc)
_PAST   = datetime(2020,  1,  1, tzinfo=timezone.utc)


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
    from main.app.domain.user.admin_invitation.service import AdminInvitationService
    svc = object.__new__(AdminInvitationService)
    svc._repo = AsyncMock()
    svc._user_repo = AsyncMock()
    svc._session_service = AsyncMock()
    return svc


def _make_invite_row(
    *,
    invite_id: str = "inv-001",
    email: str = "invitee@example.com",
    sub_role: str = AdminSubRole.OPERATIONS.value,
    status: str = AdminInvitationStatus.PENDING.value,
    expires_at: datetime = _FUTURE,
    inviter_admin_id: str = "admin-001",
):
    row = MagicMock()
    row.id = invite_id
    row.email_normalized = email
    row.sub_role = sub_role
    row.status = status
    row.expires_at = expires_at
    row.inviter_admin_id = inviter_admin_id
    row.accepted_at = None
    row.date_created = datetime(2026, 5, 7, tzinfo=timezone.utc)
    return row


def _make_user(
    *,
    user_id: str = "user-001",
    email: str = "invitee@example.com",
    user_type: str = UserType.USER.value,
):
    user = MagicMock()
    user.id = user_id
    user.email = email
    user.user_type = user_type
    return user


# ── invite ────────────────────────────────────────────────────────────────────

async def test_invite_creates_invitation_and_records_event():
    svc = _make_service()
    row = _make_invite_row()
    svc._repo.get_pending_for_email.return_value = None
    svc._repo.get_by_token_hash.return_value = row

    result = await svc.invite(
        inviter_admin_id="admin-001",
        email="invitee@example.com",
        sub_role=AdminSubRole.OPERATIONS,
    )

    svc._repo.create.assert_called_once()
    assert result.invitation.email == "invitee@example.com"
    assert result.invitation.sub_role == AdminSubRole.OPERATIONS
    assert result.raw_token  # non-empty, single-use
    svc._session_service.record_event.assert_called_once()
    evt = svc._session_service.record_event.call_args
    assert evt.kwargs["type"] == SecurityEventType.ADMIN_INVITED


async def test_invite_revokes_existing_pending_invitation():
    svc = _make_service()
    existing = _make_invite_row(invite_id="old-inv")
    new_row = _make_invite_row(invite_id="new-inv")
    svc._repo.get_pending_for_email.return_value = existing
    svc._repo.get_by_token_hash.return_value = new_row

    await svc.invite(
        inviter_admin_id="admin-001",
        email="invitee@example.com",
        sub_role=AdminSubRole.FINANCE,
    )

    # first update call must revoke the old invite
    first_update_call = svc._repo.update.call_args_list[0]
    assert first_update_call.args[0] == "old-inv"
    update_dto = first_update_call.args[1]
    assert update_dto.status == AdminInvitationStatus.REVOKED


async def test_invite_normalises_email_to_lowercase():
    svc = _make_service()
    row = _make_invite_row(email="invitee@example.com")
    svc._repo.get_pending_for_email.return_value = None
    svc._repo.get_by_token_hash.return_value = row

    result = await svc.invite(
        inviter_admin_id="admin-001",
        email="INVITEE@EXAMPLE.COM",
        sub_role=AdminSubRole.SUPER,
    )

    create_dto = svc._repo.create.call_args.args[0]
    assert create_dto.email_normalized == "invitee@example.com"


# ── accept ────────────────────────────────────────────────────────────────────

async def test_accept_empty_token_raises_validation():
    svc = _make_service()
    with pytest.raises(ValidationException):
        await svc.accept("")


async def test_accept_unknown_token_raises_not_found():
    svc = _make_service()
    svc._repo.get_by_token_hash.return_value = None

    with pytest.raises(ResourceNotFoundException):
        await svc.accept("unknown-raw-token")


async def test_accept_expired_invite_raises_and_marks_expired():
    svc = _make_service()
    invite = _make_invite_row(expires_at=_PAST)
    svc._repo.get_by_token_hash.return_value = invite

    with pytest.raises(InvalidResourceStateException, match="expired"):
        await svc.accept("some-raw-token")

    update_dto = svc._repo.update.call_args.args[1]
    assert update_dto.status == AdminInvitationStatus.EXPIRED


async def test_accept_signup_required_when_no_account():
    svc = _make_service()
    invite = _make_invite_row(email="newuser@example.com", sub_role=AdminSubRole.OPERATIONS.value)
    svc._repo.get_by_token_hash.return_value = invite
    svc._user_repo.get_by_email.return_value = None

    result = await svc.accept("raw-token")

    assert result.branch == "SIGNUP_REQUIRED"
    assert result.email == "newuser@example.com"
    assert result.sub_role == AdminSubRole.OPERATIONS
    svc._user_repo.update.assert_not_called()
    svc._repo.update.assert_not_called()


async def test_accept_login_required_when_account_exists_no_session():
    svc = _make_service()
    invite = _make_invite_row(email="existing@example.com")
    user = _make_user(user_type=UserType.USER.value)
    svc._repo.get_by_token_hash.return_value = invite
    svc._user_repo.get_by_email.return_value = user

    result = await svc.accept("raw-token", current_user_id=None)

    assert result.branch == "LOGIN_REQUIRED"
    assert result.email == "existing@example.com"
    svc._user_repo.update.assert_not_called()


async def test_accept_already_admin_when_user_already_has_admin_role():
    svc = _make_service()
    invite = _make_invite_row(email="admin@example.com")
    user = _make_user(user_type=UserType.ADMIN.value)
    svc._repo.get_by_token_hash.return_value = invite
    svc._user_repo.get_by_email.return_value = user

    result = await svc.accept("raw-token", current_user_id=None)

    assert result.branch == "ALREADY_ADMIN"
    assert result.email == "admin@example.com"
    update_dto = svc._repo.update.call_args.args[1]
    assert update_dto.status == AdminInvitationStatus.EXPIRED


async def test_accept_merges_role_when_existing_user_is_signed_in():
    svc = _make_service()
    invite = _make_invite_row(email="existing@example.com", sub_role=AdminSubRole.FINANCE.value)
    user = _make_user(user_id="user-42", user_type=UserType.USER.value)
    svc._repo.get_by_token_hash.return_value = invite
    svc._user_repo.get_by_email.return_value = user

    result = await svc.accept("raw-token", current_user_id="user-42")

    assert result.branch == "ACCEPTED"
    assert result.sub_role == AdminSubRole.FINANCE
    user_update = svc._user_repo.update.call_args.args[1]
    assert user_update.user_type == UserType.ADMIN.value
    assert user_update.admin_sub_role == AdminSubRole.FINANCE.value
    invite_update = svc._repo.update.call_args.args[1]
    assert invite_update.status == AdminInvitationStatus.ACCEPTED
    svc._session_service.record_event.assert_called_once()
    assert svc._session_service.record_event.call_args.kwargs["type"] == SecurityEventType.ADMIN_INVITE_ACCEPTED


async def test_accept_rejects_wrong_signed_in_user():
    svc = _make_service()
    invite = _make_invite_row(email="invitee@example.com")
    user = _make_user(user_id="user-A", user_type=UserType.USER.value)
    svc._repo.get_by_token_hash.return_value = invite
    svc._user_repo.get_by_email.return_value = user

    with pytest.raises(ValidationException, match="signed in as the invited email"):
        await svc.accept("raw-token", current_user_id="user-B")


# ── revoke ────────────────────────────────────────────────────────────────────

async def test_revoke_marks_pending_invite_as_revoked():
    svc = _make_service()
    invite = _make_invite_row(status=AdminInvitationStatus.PENDING.value)
    svc._repo.get_model.return_value = invite

    await svc.revoke("inv-001", admin_id="admin-001")

    update_dto = svc._repo.update.call_args.args[1]
    assert update_dto.status == AdminInvitationStatus.REVOKED
    svc._session_service.record_event.assert_called_once()
    assert svc._session_service.record_event.call_args.kwargs["type"] == SecurityEventType.ADMIN_ROLE_CHANGED


async def test_revoke_non_pending_raises():
    svc = _make_service()
    invite = _make_invite_row(status=AdminInvitationStatus.ACCEPTED.value)
    svc._repo.get_model.return_value = invite

    with pytest.raises(InvalidResourceStateException):
        await svc.revoke("inv-001", admin_id="admin-001")


async def test_revoke_missing_invite_raises():
    svc = _make_service()
    svc._repo.get_model.return_value = None

    with pytest.raises(ResourceNotFoundException):
        await svc.revoke("nonexistent", admin_id="admin-001")


# ── attach_admin_role_to_new_user ─────────────────────────────────────────────

async def test_attach_admin_role_promotes_user_on_signup():
    svc = _make_service()
    invite = _make_invite_row(sub_role=AdminSubRole.OPERATIONS.value)
    svc._repo.get_by_token_hash.return_value = invite

    await svc.attach_admin_role_to_new_user("raw-token", user_id="new-user-1")

    user_update = svc._user_repo.update.call_args.args[1]
    assert user_update.user_type == UserType.ADMIN.value
    assert user_update.admin_sub_role == AdminSubRole.OPERATIONS.value
    invite_update = svc._repo.update.call_args.args[1]
    assert invite_update.status == AdminInvitationStatus.ACCEPTED
    svc._session_service.record_event.assert_called_once()


async def test_attach_admin_role_no_ops_for_unknown_token():
    svc = _make_service()
    svc._repo.get_by_token_hash.return_value = None

    await svc.attach_admin_role_to_new_user("bad-token", user_id="user-1")

    svc._user_repo.update.assert_not_called()


async def test_attach_admin_role_no_ops_for_expired_invite():
    svc = _make_service()
    invite = _make_invite_row(expires_at=_PAST)
    svc._repo.get_by_token_hash.return_value = invite

    await svc.attach_admin_role_to_new_user("raw-token", user_id="user-1")

    svc._user_repo.update.assert_not_called()

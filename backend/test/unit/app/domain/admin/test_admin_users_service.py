"""AdminUsersService (PRD §4.2 admin user management) — repos mocked, no DB."""
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import main.app.domain.user.admin_users.service as admin_users_service_module
from main.app.core.events.events import EventType
from main.app.domain.audit.models import AuditActionType
from main.app.domain.user.admin_users.service import AdminUsersService
from main.app.domain.user.auth.session.models import UserPersona, UserType
from main.app.domain.user.models import AccountStatus, TrustStatus
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.exception.exceptions import ValidationException


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


@pytest.fixture(autouse=True)
def mock_publish_event(monkeypatch):
    published = AsyncMock()
    monkeypatch.setattr(admin_users_service_module, "publish_domain_event", published)
    return published


def _user(**over):
    base = dict(
        id=uuid.uuid4(),
        first_name="Ada",
        last_name="Lovelace",
        email="ada@example.com",
        email_verified=True,
        phone="8012345678",
        phone_country_code="NG",
        phone_dial_code="234",
        phone_verified=False,
        country_of_residence="NG",
        timezone="Africa/Lagos",
        preferred_currency="NGN",
        user_type=UserType.USER.value,
        personas=[UserPersona.CUSTOMER.value],
        admin_sub_role=None,
        trust_status=TrustStatus.UNTRUSTED.value,
        account_status=AccountStatus.ACTIVE.value,
        suspended_at=None,
        suspension_reason=None,
        suspended_by=None,
        credit_balance_kobo=0,
        referred_by=None,
        avatar_url=None,
        locked_until=None,
        deleted=False,
        date_created=datetime(2026, 7, 1, tzinfo=timezone.utc),
    )
    base.update(over)
    return SimpleNamespace(**base)


def _make_service(target_user=None):
    svc = object.__new__(AdminUsersService)
    svc._user_repo = MagicMock()
    svc._user_service = MagicMock()
    svc._session_service = MagicMock()
    svc._auth_service = MagicMock()
    svc._audit_service = MagicMock()
    svc._verification_repo = MagicMock()
    svc._payment_repo = MagicMock()

    svc._user_repo.page_users = AsyncMock(return_value=([], 0))
    svc._user_repo.suspend_user = AsyncMock()
    svc._user_repo.reactivate_user = AsyncMock()
    svc._user_service.get_user_model = AsyncMock(return_value=target_user)
    svc._user_service.set_trust_status = AsyncMock()
    svc._session_service.revoke_all_devices_for_user = AsyncMock(return_value=1)
    svc._session_service.record_event = AsyncMock()
    svc._session_service.list_recent_events = AsyncMock(return_value=[])
    svc._auth_service.request_password_reset = AsyncMock(return_value=("raw-token", "Ada Lovelace"))
    svc._verification_repo.count_by_status_for_customer = AsyncMock(return_value={})
    svc._payment_repo.count_for_customer = AsyncMock(return_value=0)
    return svc


class TestListUsers:
    async def test_forwards_filters_and_pagination(self):
        svc = _make_service()
        await svc.list_users(
            page=2, page_size=25, query="ada",
            persona=UserPersona.CUSTOMER.value,
            user_type=UserType.USER.value,
            trust_status=TrustStatus.TRUSTED.value,
            account_status=AccountStatus.SUSPENDED.value,
        )
        svc._user_repo.page_users.assert_awaited_once_with(
            offset=50, limit=25, query="ada",
            persona=UserPersona.CUSTOMER.value,
            user_type=UserType.USER.value,
            trust_status=TrustStatus.TRUSTED.value,
            account_status=AccountStatus.SUSPENDED.value,
        )

    async def test_builds_page_of_summaries(self):
        row = _user()
        svc = _make_service()
        svc._user_repo.page_users = AsyncMock(return_value=([row], 11))
        page = await svc.list_users(page=0, page_size=10)
        assert page.meta.total == 11
        assert page.meta.total_pages == 2
        item = page.items[0]
        assert item.id == row.id.hex
        assert item.name == "Ada Lovelace"
        assert item.account_status == AccountStatus.ACTIVE
        assert item.personas == [UserPersona.CUSTOMER]


class TestGetUserDetail:
    async def test_aggregates_profile_counts_and_events(self):
        row = _user()
        svc = _make_service(target_user=row)
        svc._verification_repo.count_by_status_for_customer = AsyncMock(
            return_value={"COMPLETED": 2, "IN_PROGRESS": 1}
        )
        svc._payment_repo.count_for_customer = AsyncMock(return_value=3)
        detail = await svc.get_user_detail("u-1")
        assert detail.verifications_total == 3
        assert detail.verification_counts == {"COMPLETED": 2, "IN_PROGRESS": 1}
        assert detail.payments_count == 3
        # Cross-domain lookups are keyed on the 36-char user-id form.
        svc._verification_repo.count_by_status_for_customer.assert_awaited_once_with(str(row.id))
        svc._payment_repo.count_for_customer.assert_awaited_once_with(str(row.id))
        svc._session_service.list_recent_events.assert_awaited_once()


class TestSuspend:
    async def test_suspends_revokes_sessions_audits_and_notifies(self, mock_publish_event):
        row = _user()
        svc = _make_service(target_user=row)
        await svc.suspend(str(row.id), reason="Chargeback fraud pattern", admin_id="admin-1")

        svc._user_repo.suspend_user.assert_awaited_once()
        kwargs = svc._user_repo.suspend_user.call_args.kwargs
        assert kwargs["reason"] == "Chargeback fraud pattern"
        assert kwargs["admin_id"] == "admin-1"

        svc._session_service.revoke_all_devices_for_user.assert_awaited_once_with(str(row.id))

        audit = svc._audit_service.schedule.call_args.kwargs
        assert audit["action"] == AuditActionType.USER_SUSPENDED
        assert audit["from_state"] == AccountStatus.ACTIVE.value
        assert audit["to_state"] == AccountStatus.SUSPENDED.value
        assert audit["actor_id"] == "admin-1"

        event = mock_publish_event.call_args.args[0]
        assert event.type == EventType.ACCOUNT_SUSPENDED
        assert event.recipient_user_ids == (str(row.id),)

    async def test_cannot_suspend_self(self):
        row = _user()
        svc = _make_service(target_user=row)
        with pytest.raises(ValidationException):
            await svc.suspend(str(row.id), reason="reason enough", admin_id=str(row.id))
        svc._user_repo.suspend_user.assert_not_awaited()

    async def test_cannot_suspend_admin_account(self):
        row = _user(user_type=UserType.ADMIN.value)
        svc = _make_service(target_user=row)
        with pytest.raises(ValidationException):
            await svc.suspend(str(row.id), reason="reason enough", admin_id="admin-1")
        svc._user_repo.suspend_user.assert_not_awaited()

    async def test_cannot_suspend_already_suspended(self):
        row = _user(account_status=AccountStatus.SUSPENDED.value)
        svc = _make_service(target_user=row)
        with pytest.raises(ValidationException):
            await svc.suspend(str(row.id), reason="reason enough", admin_id="admin-1")
        svc._user_repo.suspend_user.assert_not_awaited()


class TestReactivate:
    async def test_reactivates_audits_and_notifies(self, mock_publish_event):
        row = _user(account_status=AccountStatus.SUSPENDED.value)
        svc = _make_service(target_user=row)
        await svc.reactivate(str(row.id), admin_id="admin-1")

        svc._user_repo.reactivate_user.assert_awaited_once()
        audit = svc._audit_service.schedule.call_args.kwargs
        assert audit["action"] == AuditActionType.USER_REACTIVATED
        assert audit["from_state"] == AccountStatus.SUSPENDED.value
        assert audit["to_state"] == AccountStatus.ACTIVE.value

        event = mock_publish_event.call_args.args[0]
        assert event.type == EventType.ACCOUNT_REACTIVATED

    async def test_cannot_reactivate_active_account(self):
        row = _user()
        svc = _make_service(target_user=row)
        with pytest.raises(ValidationException):
            await svc.reactivate(str(row.id), admin_id="admin-1")
        svc._user_repo.reactivate_user.assert_not_awaited()


class TestForcePasswordReset:
    async def test_issues_reset_revokes_sessions_and_audits(self):
        row = _user()
        svc = _make_service(target_user=row)
        issued = await svc.force_password_reset(str(row.id), admin_id="admin-1")

        svc._auth_service.request_password_reset.assert_awaited_once_with(row.email)
        svc._session_service.revoke_all_devices_for_user.assert_awaited_once_with(str(row.id))
        audit = svc._audit_service.schedule.call_args.kwargs
        assert audit["action"] == AuditActionType.PASSWORD_RESET_FORCED
        assert issued is not None
        assert issued.raw_token == "raw-token"
        assert issued.email == row.email


class TestSetTrustStatus:
    async def test_sets_and_audits_downgrade(self):
        row = _user(trust_status=TrustStatus.TRUSTED.value)
        svc = _make_service(target_user=row)
        await svc.set_trust_status(str(row.id), TrustStatus.UNTRUSTED, admin_id="admin-1")

        svc._user_service.set_trust_status.assert_awaited_once_with(str(row.id), TrustStatus.UNTRUSTED)
        audit = svc._audit_service.schedule.call_args.kwargs
        assert audit["action"] == AuditActionType.TRUST_STATUS_CHANGED
        assert audit["from_state"] == TrustStatus.TRUSTED.value
        assert audit["to_state"] == TrustStatus.UNTRUSTED.value

    async def test_rejects_no_op_change(self):
        row = _user(trust_status=TrustStatus.TRUSTED.value)
        svc = _make_service(target_user=row)
        with pytest.raises(ValidationException):
            await svc.set_trust_status(str(row.id), TrustStatus.TRUSTED, admin_id="admin-1")
        svc._user_service.set_trust_status.assert_not_awaited()

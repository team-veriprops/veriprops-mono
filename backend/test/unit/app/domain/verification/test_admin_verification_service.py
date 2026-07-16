"""AdminVerificationService (§6.1–§6.4): SLA health, detail composition, assignment
delegation, pause/resume flag, cancel transition guard, SLA delay, notes. Deps mocked."""
from contextlib import asynccontextmanager
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.core.sla import add_business_days
from main.app.core.state.status import AgentRole, VerificationStatus, VerificationTier
from main.app.domain.audit.models import AuditActionType
from main.app.domain.verification.admin.models import (
    CancelVerificationDto,
    SetDelayDto,
    SlaHealth,
)
from main.app.domain.verification.admin.service import AdminVerificationService
from main.app.domain.verification.admin_note.models import AddAdminNoteDto, AdminNoteCategory
from main.appodus_utils import Utils
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.exception.exceptions import InvalidResourceStateException


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


def _verification(status=VerificationStatus.IN_PROGRESS, tier=VerificationTier.STANDARD, due=None):
    return SimpleNamespace(
        id="v-1", vid="VP-ABC123", customer_id="cust-1", property_id=None,
        tier=tier.value, status=status.value, paused=False,
        sla_due_date=due, date_created=Utils.datetime_now(),
    )


def _make_service(verification):
    svc = object.__new__(AdminVerificationService)
    svc._verification_repo = MagicMock()
    svc._property_repo = MagicMock()
    svc._payment_repo = MagicMock()
    svc._task_service = MagicMock()
    svc._notes = MagicMock()
    svc._commissions = MagicMock()
    svc._chargebacks = MagicMock()
    svc._audit = MagicMock()

    svc._verification_repo.get_model = AsyncMock(return_value=verification)
    svc._verification_repo.update = AsyncMock()
    svc._property_repo.get_model = AsyncMock(return_value=None)
    svc._payment_repo.list_for_verification = AsyncMock(return_value=[])
    svc._task_service.list_for_verification = AsyncMock(return_value=[])
    svc._task_service.assign = AsyncMock()
    svc._notes.list_for_verification = AsyncMock(return_value=[])
    svc._notes.add = AsyncMock(return_value=SimpleNamespace(id="n-1"))
    svc._commissions.list_for_verification = AsyncMock(return_value=[])
    svc._chargebacks.list_for_verification = AsyncMock(return_value=[])
    return svc


class TestDashboardSummary:
    def _summary_service(self, status_counts, recent_rows):
        svc = object.__new__(AdminVerificationService)
        svc._verification_repo = MagicMock()
        svc._property_repo = MagicMock()
        svc._payment_repo = MagicMock()
        svc._task_service = MagicMock()
        svc._agents = MagicMock()
        svc._chargebacks = MagicMock()
        svc._config = AsyncMock()
        svc._config.get_int = AsyncMock(return_value=2)  # SLA_AT_RISK_DAYS default
        svc._verification_repo.count_by_status = AsyncMock(return_value=status_counts)
        svc._verification_repo.count_overdue = AsyncMock(return_value=3)
        svc._verification_repo.count_due_within = AsyncMock(return_value=6)
        svc._verification_repo.page_admin = AsyncMock(return_value=(list(recent_rows), len(recent_rows)))
        svc._property_repo.get_model = AsyncMock(return_value=None)
        svc._payment_repo.sum_succeeded_amount = AsyncMock(return_value=99_000_000)
        svc._task_service.count_pool_pending = AsyncMock(return_value=4)
        svc._agents.count_pending_applications = AsyncMock(return_value=2)
        svc._agents.count_available_agents = AsyncMock(return_value=7)
        svc._chargebacks.count_open = AsyncMock(return_value=1)
        return svc

    async def test_summary_aggregates_all_sources(self):
        counts = {
            VerificationStatus.PAID.value: 2,
            VerificationStatus.IN_PROGRESS.value: 5,
            VerificationStatus.COMPLETED.value: 10,
        }
        svc = self._summary_service(counts, [_verification()])
        dto = await svc.summary()

        assert dto.total == 17
        assert dto.status_counts[VerificationStatus.IN_PROGRESS] == 5
        assert dto.overdue == 3
        assert dto.sla_at_risk == 6
        assert dto.unassigned_pool_tasks == 4
        assert dto.pending_agent_applications == 2
        assert dto.open_chargebacks == 1
        assert dto.available_agents == 7
        assert dto.revenue_minor == 99_000_000
        assert len(dto.recent) == 1
        # overdue is computed against the SLA-active statuses only
        _, kwargs = svc._verification_repo.count_overdue.call_args
        assert not kwargs  # positional call
        active_arg = svc._verification_repo.count_overdue.call_args.args[0]
        assert VerificationStatus.IN_PROGRESS.value in active_arg


class TestSlaHealth:
    def test_none_when_no_clock(self):
        svc = _make_service(_verification(status=VerificationStatus.PAID, due=None))
        health, remaining = svc._sla_health(svc._verification_repo.get_model.return_value)
        assert health == SlaHealth.NONE
        assert remaining is None

    def test_overdue_when_past_due(self):
        past = Utils.datetime_now().date() - timedelta(days=5)
        svc = _make_service(_verification(due=past))
        health, remaining = svc._sla_health(svc._verification_repo.get_model.return_value)
        assert health == SlaHealth.OVERDUE
        assert remaining < 0

    def test_on_track_when_far_out(self):
        far = add_business_days(Utils.datetime_now().date(), 10)
        svc = _make_service(_verification(due=far))
        health, _ = svc._sla_health(svc._verification_repo.get_model.return_value)
        assert health == SlaHealth.ON_TRACK


class TestActions:
    async def test_assign_delegates_to_task_service(self):
        svc = _make_service(_verification())
        await svc.assign("v-1", AgentRole.FIELD, "agent-1", "admin-1")
        svc._task_service.assign.assert_awaited_once_with("v-1", AgentRole.FIELD, "agent-1", "admin-1")

    async def test_pause_sets_flag_and_audits(self):
        v = _verification()
        svc = _make_service(v)
        await svc.pause("v-1", "admin-1")
        assert v.paused is True
        actions = [c.kwargs["action"] for c in svc._audit.schedule.call_args_list]
        assert AuditActionType.VERIFICATION_PAUSED in actions

    async def test_resume_clears_flag(self):
        v = _verification()
        v.paused = True
        svc = _make_service(v)
        await svc.resume("v-1", "admin-1")
        assert v.paused is False

    async def test_cancel_rejects_from_terminal(self):
        svc = _make_service(_verification(status=VerificationStatus.COMPLETED))
        with pytest.raises(InvalidResourceStateException):
            await svc.cancel("v-1", CancelVerificationDto(reason="dup"), "admin-1")

    async def test_set_delay_extends_due_date(self):
        due = add_business_days(Utils.datetime_now().date(), 3)
        v = _verification(due=due)
        svc = _make_service(v)
        await svc.set_delay("v-1", SetDelayDto(extra_business_days=2, reason="holiday"), "admin-1")
        assert v.sla_due_date == add_business_days(due, 2)

    async def test_set_delay_without_clock_rejected(self):
        svc = _make_service(_verification(due=None))
        with pytest.raises(InvalidResourceStateException):
            await svc.set_delay("v-1", SetDelayDto(extra_business_days=2), "admin-1")

    async def test_add_note_delegates_and_audits(self):
        svc = _make_service(_verification())
        await svc.add_note(
            "v-1", AddAdminNoteDto(category=AdminNoteCategory.RISK, body="watch this"), "admin-1"
        )
        svc._notes.add.assert_awaited_once()
        actions = [c.kwargs["action"] for c in svc._audit.schedule.call_args_list]
        assert AuditActionType.ADMIN_NOTE_ADDED in actions

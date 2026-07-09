"""CommissionService — freeze / unfreeze / reverse operations that back the
chargeback sub-process (§6a.2). Repos mocked, no DB."""
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.core.state.status import AgentRole, VerificationTier
from main.app.domain.audit.models import AuditActionType
from main.app.domain.commission.models import CommissionStatus
from main.app.domain.commission.service import CommissionService
from main.appodus_utils.db.session import db_session_ctx


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


def _commission(status=CommissionStatus.CLEARING, cid="c-1", frozen_from=None):
    return SimpleNamespace(
        id=cid, verification_id="v-1", task_id="t-1", agent_id="a-1",
        role=AgentRole.FIELD.value, tier=VerificationTier.STANDARD.value,
        amount_minor=500000, currency="NGN", status=status.value,
        clearing_until=None, frozen_from_status=frozen_from,
    )


def _make_service(commissions):
    svc = object.__new__(CommissionService)
    svc._commission_repo = MagicMock()
    svc._audit = MagicMock()
    state = {"rows": list(commissions)}

    async def _list_in_status(vid, statuses):
        return [c for c in state["rows"] if c.status in statuses]

    async def _update(cid, dto):
        c = next((c for c in state["rows"] if c.id == cid), None)
        if c is not None:
            for f, v in dto.model_dump(exclude_none=True).items():
                setattr(c, f, v)
        return c

    svc._commission_repo.list_for_verification_in_status = AsyncMock(side_effect=_list_in_status)
    svc._commission_repo.list_for_verification = AsyncMock(side_effect=lambda vid: list(state["rows"]))
    svc._commission_repo.update = AsyncMock(side_effect=_update)
    svc._state = state
    return svc


class TestFreeze:
    async def test_freezes_clearing_and_available_only(self):
        rows = [
            _commission(CommissionStatus.CLEARING, "c-1"),
            _commission(CommissionStatus.AVAILABLE, "c-2"),
            _commission(CommissionStatus.REVERSED, "c-3"),
        ]
        svc = _make_service(rows)
        count = await svc.freeze_for_verification("v-1", actor_id="admin-1")
        assert count == 2
        assert rows[0].status == CommissionStatus.FROZEN.value
        assert rows[1].status == CommissionStatus.FROZEN.value
        assert rows[2].status == CommissionStatus.REVERSED.value  # untouched

    async def test_freeze_captures_prior_status(self):
        rows = [_commission(CommissionStatus.AVAILABLE, "c-1")]
        svc = _make_service(rows)
        await svc.freeze_for_verification("v-1", actor_id="admin-1")
        assert rows[0].frozen_from_status == CommissionStatus.AVAILABLE.value

    async def test_freeze_audits(self):
        svc = _make_service([_commission(CommissionStatus.CLEARING)])
        await svc.freeze_for_verification("v-1", actor_id="admin-1")
        actions = [c.kwargs["action"] for c in svc._audit.schedule.call_args_list]
        assert AuditActionType.COMMISSION_FROZEN in actions


class TestUnfreeze:
    async def test_restores_prior_status(self):
        rows = [_commission(CommissionStatus.FROZEN, "c-1", frozen_from=CommissionStatus.AVAILABLE.value)]
        svc = _make_service(rows)
        count = await svc.unfreeze_for_verification("v-1", actor_id="admin-1")
        assert count == 1
        assert rows[0].status == CommissionStatus.AVAILABLE.value

    async def test_defaults_to_clearing_when_no_prior(self):
        rows = [_commission(CommissionStatus.FROZEN, "c-1", frozen_from=None)]
        svc = _make_service(rows)
        await svc.unfreeze_for_verification("v-1", actor_id="admin-1")
        assert rows[0].status == CommissionStatus.CLEARING.value


class TestReverse:
    async def test_reverses_frozen_and_exposed(self):
        rows = [
            _commission(CommissionStatus.FROZEN, "c-1"),
            _commission(CommissionStatus.CLEARING, "c-2"),
        ]
        svc = _make_service(rows)
        count = await svc.reverse_for_verification("v-1", actor_id="admin-1")
        assert count == 2
        assert all(c.status == CommissionStatus.REVERSED.value for c in rows)

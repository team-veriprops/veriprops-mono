"""CommissionRuleService — the fixed per-role agent commission (§20.1 / D97). Repos mocked,
no DB. Default-amount seeding is done by migration 0002 and guarded by
test_migration_seed_parity.py."""
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.core.state.status import AgentRole
from main.app.domain.commission_rule.service import CommissionRuleService
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.exception.exceptions import ValidationException
from test.utils.repo_fakes import fake_upsert


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


def _make_service(amounts_by_role=None):
    svc = object.__new__(CommissionRuleService)
    svc._rule_repo = AsyncMock()
    svc._audit = SimpleNamespace(schedule=MagicMock())
    svc._margin_guard = AsyncMock()
    rules = {
        role.value: SimpleNamespace(id=f"rule-{role.value}", role=role.value, amount_ngn_kobo=amount)
        for role, amount in (amounts_by_role or {}).items()
    }

    async def _get(role):
        return rules.get(role)

    svc._rule_repo.get_for_role = AsyncMock(side_effect=_get)
    svc._rule_repo.list_all = AsyncMock(return_value=list(rules.values()))
    return svc


class TestCommissionMinor:
    async def test_commission_is_the_roles_fixed_amount(self):
        svc = _make_service({AgentRole.REGISTRY: 2_000_000})
        assert await svc.commission_minor(AgentRole.REGISTRY) == 2_000_000

    async def test_missing_rule_yields_zero(self):
        svc = _make_service({})
        assert await svc.commission_minor(AgentRole.LAWYER) == 0

    async def test_commission_by_role_covers_every_role_in_one_read(self):
        svc = _make_service({AgentRole.FIELD: 1_440_000, AgentRole.LAWYER: 3_600_000})
        by_role = await svc.commission_by_role()
        assert by_role == {
            AgentRole.REGISTRY: 0, AgentRole.FIELD: 1_440_000,
            AgentRole.SURVEYOR: 0, AgentRole.LAWYER: 3_600_000,
        }
        svc._rule_repo.list_all.assert_awaited_once()


class TestSetRule:
    async def test_set_rule_upserts_the_role_amount_and_audits(self):
        svc = _make_service({})
        svc._rule_repo.upsert = fake_upsert(
            lambda _values: None, lambda values: SimpleNamespace(id="rule-1", **values)
        )
        row = await svc.set_rule(AgentRole.SURVEYOR, 1_500_000, "admin-1")
        assert (row.role, row.amount_ngn_kobo) == (AgentRole.SURVEYOR.value, 1_500_000)
        details = svc._audit.schedule.call_args.kwargs["details"]
        assert details == {"role": AgentRole.SURVEYOR.value, "amount_ngn_kobo": 1_500_000}

    async def test_the_proposed_amount_is_checked_against_every_tiers_margin(self):
        svc = _make_service({})
        svc._rule_repo.upsert = AsyncMock(return_value=SimpleNamespace(id="rule-1"))
        await svc.set_rule(AgentRole.LAWYER, 3_000_000, "admin-1")
        svc._margin_guard.check.assert_awaited_once_with(commission_overrides={AgentRole.LAWYER: 3_000_000})

    async def test_an_amount_that_breaks_a_tiers_margin_is_never_written(self):
        svc = _make_service({})
        svc._rule_repo.upsert = AsyncMock()
        svc._margin_guard.check = AsyncMock(side_effect=ValidationException(message="below the margin"))
        with pytest.raises(ValidationException):
            await svc.set_rule(AgentRole.REGISTRY, 9_000_000, "admin-1")
        svc._rule_repo.upsert.assert_not_awaited()

    async def test_negative_amount_is_refused(self):
        svc = _make_service({})
        svc._rule_repo.upsert = AsyncMock()
        with pytest.raises(ValidationException):
            await svc.set_rule(AgentRole.FIELD, -1, "admin-1")
        svc._rule_repo.upsert.assert_not_awaited()

"""The tools for status changes that must happen once, however many requests race for them.

- `GenericRepo.claim_transition`: move a row out of an expected status in one conditional
  `UPDATE … WHERE status IN (…) RETURNING`. Exactly one concurrent caller gets the row back;
  the others get None and must not repeat the side effects that follow the move.
- `GenericRepo.lock_model`: read a row `FOR UPDATE`, for a multi-step decision (a release)
  whose end state is derived rather than known up front.
- `StateMachine.sources_of`: every state a target may be reached from — the `from` set of
  a claim, read off the one transition table.
"""
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.dialects import postgresql

from main.app.core.state.machine import verification_state_machine
from main.app.core.state.status import VerificationStatus
from main.app.domain.payout.models import Payout, PayoutStatus
from main.appodus_utils.db.models import Object
from main.appodus_utils.db.repo import GenericRepo
from main.appodus_utils.db.session import db_session_ctx
from test.utils.repo_fakes import fake_claim_transition


class _Dto(Object):
    id: str


@pytest.fixture
def session():
    s = MagicMock()
    s.statements = []

    async def _execute(stmt, *args, **kwargs):
        s.statements.append(stmt)
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        return result

    s.execute = AsyncMock(side_effect=_execute)
    s.flush = AsyncMock()
    token = db_session_ctx.set(s)
    yield s
    db_session_ctx.reset(token)


def _compiled(stmt):
    return stmt.compile(dialect=postgresql.dialect())


def _sql(stmt) -> str:
    return " ".join(str(_compiled(stmt)).split())


PAYOUT_ID = uuid.UUID("0199a000-0000-7000-8000-000000000001")


async def test_claim_is_one_conditional_update_returning_the_row(session):
    repo = GenericRepo(db=None, model=Payout, query_qto=_Dto)

    await repo.claim_transition(
        PAYOUT_ID.hex, [PayoutStatus.REQUESTED, PayoutStatus.HELD], PayoutStatus.PAID, decided_by="fin-1",
    )

    [stmt] = session.statements
    sql = _sql(stmt)
    assert sql.startswith("UPDATE payouts SET")
    assert "WHERE payouts.id = %(id_1)s::UUID AND payouts.deleted IS false AND payouts.status IN" in sql
    assert "version=(payouts.version + %(version_1)s)" in sql
    assert "RETURNING" in sql
    params = _compiled(stmt).params
    # Enum members bind as their stored strings, whichever form the caller passes.
    assert params["status"] == PayoutStatus.PAID.value
    assert params["status_1"] == [PayoutStatus.REQUESTED.value, PayoutStatus.HELD.value]
    assert params["decided_by"] == "fin-1"
    assert params["id_1"] == PAYOUT_ID
    # The loser's session must not keep a stale copy of the row it failed to claim.
    assert stmt.get_execution_options().get("populate_existing") is True


async def test_a_lost_claim_returns_none(session):
    repo = GenericRepo(db=None, model=Payout, query_qto=_Dto)

    assert await repo.claim_transition(PAYOUT_ID, [PayoutStatus.REQUESTED], PayoutStatus.CANCELLED) is None


async def test_expect_pins_the_fields_the_decision_was_made_on(session):
    repo = GenericRepo(db=None, model=Payout, query_qto=_Dto)

    await repo.claim_transition(
        PAYOUT_ID, [PayoutStatus.REQUESTED], PayoutStatus.CANCELLED,
        expect={"agent_id": "a-1", "note": None},
    )

    sql = _sql(session.statements[0])
    assert "payouts.agent_id = %(agent_id_1)s" in sql
    assert "payouts.note IS NULL" in sql


async def test_increments_are_computed_in_sql(session):
    repo = GenericRepo(db=None, model=Payout, query_qto=_Dto)

    await repo.claim_transition(PAYOUT_ID, [PayoutStatus.HELD], increments={"adjustment_minor": 5})

    sql = _sql(session.statements[0])
    assert "adjustment_minor=(coalesce(payouts.adjustment_minor, %(coalesce_1)s) + %(coalesce_2)s)" in sql
    # No target status: the row is updated only while still in one of the given statuses.
    assert "status=" not in sql.split(" WHERE ")[0]


async def test_lock_model_reads_the_live_row_for_update(session):
    repo = GenericRepo(db=None, model=Payout, query_qto=_Dto)

    await repo.lock_model(PAYOUT_ID.hex)

    [stmt] = session.statements
    sql = _sql(stmt)
    assert sql.startswith("SELECT")
    assert "WHERE payouts.id = %(id_1)s::UUID AND payouts.deleted IS false FOR UPDATE" in sql
    assert stmt.get_execution_options().get("populate_existing") is True


def test_sources_of_lists_every_state_that_may_move_to_the_target():
    sources = verification_state_machine.sources_of(VerificationStatus.PAID.value)

    assert sources == {VerificationStatus.PAYMENT_PENDING.value}
    for state in sources:
        verification_state_machine.assert_can_transition(state, VerificationStatus.PAID.value)


def test_sources_of_never_includes_a_terminal_state():
    for target in VerificationStatus:
        for state in verification_state_machine.sources_of(target.value):
            assert not verification_state_machine.is_terminal(state)


class TestFake:
    """The in-memory claim the service tests use honours the same contract."""

    async def test_first_claim_wins_and_the_second_gets_none(self):
        row = MagicMock(id="p-1", status=PayoutStatus.REQUESTED.value, adjustment_minor=0)
        claim = fake_claim_transition({"p-1": row})

        first = await claim("p-1", [PayoutStatus.REQUESTED], PayoutStatus.PAID, increments={"adjustment_minor": 3})
        second = await claim("p-1", [PayoutStatus.REQUESTED], PayoutStatus.PAID)

        assert first is row and row.status == PayoutStatus.PAID.value
        assert row.adjustment_minor == 3
        assert second is None

    async def test_expectation_mismatch_loses(self):
        row = MagicMock(id="p-1", status=PayoutStatus.REQUESTED.value, agent_id="a-2")
        claim = fake_claim_transition({"p-1": row})

        assert await claim("p-1", [PayoutStatus.REQUESTED], PayoutStatus.CANCELLED, expect={"agent_id": "a-1"}) is None
        assert row.status == PayoutStatus.REQUESTED.value


class TestPendingChangesSurvive:
    """Sessions here run with autoflush off, and these statements reload the rows they touch
    (`populate_existing`). An edit made in memory just before them — a dispute setting
    IN_PROGRESS, then reopening a task under the verification lock — would be silently
    replaced by the database's copy. So each flushes the session first."""

    @pytest.fixture
    def ordered(self):
        s = MagicMock()
        s.calls = []

        async def _flush():
            s.calls.append("flush")

        async def _execute(stmt, *args, **kwargs):
            s.calls.append("execute")
            result = MagicMock()
            result.scalar_one_or_none.return_value = None
            result.scalar_one.return_value = MagicMock()
            return result

        s.flush = AsyncMock(side_effect=_flush)
        s.execute = AsyncMock(side_effect=_execute)
        token = db_session_ctx.set(s)
        yield s
        db_session_ctx.reset(token)

    async def test_claim_flushes_before_it_updates(self, ordered):
        await GenericRepo(db=None, model=Payout, query_qto=_Dto).claim_transition(
            PAYOUT_ID, [PayoutStatus.REQUESTED], PayoutStatus.PAID,
        )
        assert ordered.calls == ["flush", "execute"]

    async def test_lock_flushes_before_it_reloads(self, ordered):
        await GenericRepo(db=None, model=Payout, query_qto=_Dto).lock_model(PAYOUT_ID)
        assert ordered.calls == ["flush", "execute"]

    async def test_upsert_flushes_before_it_writes(self, ordered):
        from main.app.domain.system_config.models import SystemConfig

        await GenericRepo(db=None, model=SystemConfig, query_qto=_Dto).upsert(
            {"key": "k", "value_json": 1}, ["value_json"], unique_index="uq_system_config_key",
        )
        assert ordered.calls == ["flush", "execute"]

    async def test_persona_grant_and_reset_consume_flush_first(self, ordered):
        from datetime import datetime, timezone

        from main.app.domain.user.auth.session.models import UserPersona
        from main.app.domain.user.auth.session.repo import PasswordResetTokenRepo
        from main.app.domain.user.repo import UserRepo

        await UserRepo(db=None).add_persona(PAYOUT_ID.hex, UserPersona.AGENT)
        await PasswordResetTokenRepo(db=None).consume("h", datetime.now(timezone.utc))
        assert ordered.calls == ["flush", "execute", "flush", "execute"]

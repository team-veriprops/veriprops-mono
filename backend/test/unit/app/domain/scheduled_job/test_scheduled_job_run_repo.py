"""ScheduledJobRunRepo.claim_run — one `UPDATE … WHERE last_run_at <is what we read>`.

Compare-and-set on the timestamp the due decision rested on: a concurrent tick that already
moved it makes this one match no row, and so lose.
"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.dialects import postgresql

from main.app.domain.scheduled_job.repo import ScheduledJobRunRepo
from main.appodus_utils.db.session import db_session_ctx
from test.utils.db_session import mock_db_session  # noqa: F401  (autouse fixture)

AT = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)


def _repo(returned) -> ScheduledJobRunRepo:
    result = MagicMock()
    result.scalar.return_value = returned
    db_session_ctx.get().execute = AsyncMock(return_value=result)
    return object.__new__(ScheduledJobRunRepo)


def _sql() -> str:
    stmt = db_session_ctx.get().execute.call_args.args[0]
    return str(stmt.compile(dialect=postgresql.dialect()))


@pytest.mark.parametrize("returned, won", [("job", True), (None, False)])
async def test_it_reports_whether_this_caller_moved_the_row(returned, won):
    repo = _repo(returned)

    assert await repo.claim_run("job", expected_last_run_at=AT, at=AT) is won


async def test_a_never_run_job_is_claimed_only_while_it_is_still_never_run():
    repo = _repo("job")

    await repo.claim_run("job", expected_last_run_at=None, at=AT)

    sql = _sql()
    assert sql.startswith("UPDATE scheduled_job_runs")
    assert "scheduled_job_runs.last_run_at IS NULL" in sql
    assert "scheduled_job_runs.deleted IS false" in sql


async def test_a_run_job_is_claimed_only_while_its_last_run_is_unchanged():
    repo = _repo("job")

    await repo.claim_run("job", expected_last_run_at=AT, at=AT)

    assert "scheduled_job_runs.last_run_at = %(last_run_at_1)s" in _sql()

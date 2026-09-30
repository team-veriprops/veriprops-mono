"""PaymentRepo.page_refunds_to_retry: the SQL behind finance's refunds-to-retry list.

An approved refund the gateway refused leaves its charge SUCCEEDED and still owing what it was
asked for (`refund_due_minor`). The query finds exactly those: live, settled charges owing money,
not under a chargeback, oldest first. What is owed is recorded, never inferred from the case's
status — a failed case with nothing approved owes nothing.
"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.domain.payment.models import Payment
from main.app.domain.payment.repo import PaymentRepo
from main.appodus_utils.db.session import db_session_ctx


@pytest.fixture
def session():
    session = MagicMock()
    token = db_session_ctx.set(session)
    yield session
    db_session_ctx.reset(token)


def _sql(stmt) -> str:
    return " ".join(str(stmt.compile(compile_kwargs={"literal_binds": True})).lower().split())


async def test_it_lists_settled_charges_still_owing_an_approved_refund(session):
    rows = MagicMock()
    rows.scalars.return_value.all.return_value = ["p1"]
    session.scalar = AsyncMock(return_value=7)
    session.execute = AsyncMock(return_value=rows)
    repo = object.__new__(PaymentRepo)
    repo._model = Payment

    page_rows, total = await repo.page_refunds_to_retry(page=1, page_size=5)

    assert (page_rows, total) == (["p1"], 7)
    sql = _sql(session.execute.await_args.args[0])
    assert "payments.deleted is false" in sql
    assert "payments.status = 'succeeded'" in sql
    # A payment under a chargeback is the issuer's to settle, never ours to refund.
    assert "payments.chargeback_status is null" in sql
    assert "payments.refund_due_minor > 0" in sql
    assert "verifications" not in sql
    assert "order by payments.date_created asc" in sql
    assert "limit 5 offset 5" in sql

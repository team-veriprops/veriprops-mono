"""PaymentRepo.sum_collected_revenue: what Veriprops kept (Finance landing, Mission Control §18.1).

A settled charge counts in full. A refunded one counts for what the refund did not return —
nothing after a full refund, the surcharge after a customer withdrew (a partial refund) — so
money kept is never lost from revenue because its charge is marked REFUNDED.
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


async def test_revenue_counts_settled_charges_and_what_a_refund_kept(session):
    session.scalar = AsyncMock(return_value=4_200_000)
    repo = object.__new__(PaymentRepo)
    repo._model = Payment

    assert await repo.sum_collected_revenue() == 4_200_000

    sql = _sql(session.scalar.await_args.args[0])
    assert "when (payments.status = 'succeeded') then payments.amount_minor" in sql
    assert "when (payments.status = 'refunded') then payments.amount_minor - coalesce(payments.refunded_amount_minor, payments.amount_minor)" in sql
    assert "payments.deleted is false" in sql

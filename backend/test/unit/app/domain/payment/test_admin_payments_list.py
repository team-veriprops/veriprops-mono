"""Finance's payments list (§18.1): every charge, newest first, searchable and filterable.

Nothing else shows one payment's own state (paid, refunded, a refund the gateway refused, under
a chargeback), so this list is where finance looks. Search and filter run in SQL over the whole
table (the pagination convention), matching a reference or the case's VID.
"""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.domain.payment.models import AdminPaymentDto, Payment, PaymentDto, PaymentStatus, admin_payment_to_dto
from main.app.domain.payment.repo import PaymentRepo
from main.app.domain.payment.service import PaymentService
from main.appodus_utils.db.db_utils import DbUtils
from main.appodus_utils.db.session import db_session_ctx


@pytest.fixture
def session():
    session = MagicMock()
    token = db_session_ctx.set(session)
    yield session
    db_session_ctx.reset(token)


def _sql(stmt) -> str:
    return " ".join(str(stmt.compile(compile_kwargs={"literal_binds": True})).lower().split())


def _repo(session, rows):
    result = MagicMock()
    result.all.return_value = rows
    session.scalar = AsyncMock(return_value=len(rows))
    session.execute = AsyncMock(return_value=result)
    repo = object.__new__(PaymentRepo)
    repo._model = Payment
    repo._db_utils = DbUtils(model=Payment, query_qto=PaymentDto)
    return repo


async def test_it_pages_every_payment_newest_first_with_its_vid(session):
    repo = _repo(session, [("p1", "VP-1")])

    rows, total, applied = await repo.page_for_admin(page=2, page_size=10)

    assert (rows, total, applied) == ([("p1", "VP-1")], 1, "dateCreated desc")
    sql = _sql(session.execute.await_args.args[0])
    assert "replace(cast(verifications.id as varchar), '-', '') = payments.verification_id" in sql
    assert "payments.deleted is false" in sql
    assert "order by payments.date_created desc, payments.id asc" in sql
    assert "limit 10 offset 20" in sql
    assert "payments.status =" not in sql


async def test_it_filters_by_status_and_searches_reference_or_vid(session):
    repo = _repo(session, [])

    await repo.page_for_admin(page=0, page_size=10, query="VP-7", status=PaymentStatus.REFUNDED)

    sql = _sql(session.execute.await_args.args[0])
    assert "payments.status = 'refunded'" in sql
    assert "lower(payments.tx_ref) like '%' || lower('vp-7') || '%' escape '/'" in sql
    assert "lower(verifications.vid) like '%' || lower('vp-7') || '%' escape '/'" in sql


async def test_a_client_sort_orders_by_an_allowed_column(session):
    repo = _repo(session, [])

    *_, applied = await repo.page_for_admin(page=0, page_size=10, order_by="amountMinor asc")

    assert applied == "amountMinor asc"
    assert "order by payments.amount_minor asc, payments.id asc" in _sql(session.execute.await_args.args[0])


async def test_a_sort_outside_the_allowlist_falls_back_to_newest_first(session):
    repo = _repo(session, [])

    *_, applied = await repo.page_for_admin(page=0, page_size=10, order_by="customerId asc")

    assert applied == "dateCreated desc"
    assert "order by payments.date_created desc" in _sql(session.execute.await_args.args[0])


async def test_a_search_cannot_widen_itself_with_wildcards(session):
    repo = _repo(session, [])

    await repo.page_for_admin(page=0, page_size=10, query="%")

    sql = _sql(session.execute.await_args.args[0])
    # The typed "%" is escaped to a literal percent sign, not a match-everything wildcard.
    assert "lower('/%')" in sql and "escape '/'" in sql


def _payment(**over):
    base = dict(
        id="p1", verification_id="v1", customer_id="c1", tx_ref="VP-1-abc", method="CARD", purpose="INITIAL",
        status=PaymentStatus.SUCCEEDED.value, amount_minor=1_500_000, currency="NGN", charge_currency=None,
        charge_amount_minor=None, checkout_url=None, provider="flutterwave", gateway_reference="FLW-1",
        refunded_amount_minor=None, refund_due_minor=None, chargeback_status=None,
        date_created=datetime(2026, 9, 29, tzinfo=timezone.utc),
    )
    base.update(over)
    return SimpleNamespace(**base)


def test_a_row_carries_what_finance_reads_a_payment_by():
    row = admin_payment_to_dto(_payment(chargeback_status="FLAGGED"), "VP-1")

    assert isinstance(row, AdminPaymentDto)
    assert (row.vid, row.provider, row.gateway_reference, row.chargeback_status) == ("VP-1", "flutterwave", "FLW-1", "FLAGGED")


async def test_the_service_returns_a_page_of_rows(session):
    session.in_transaction.return_value = False
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _begin():
        yield

    session.begin = _begin
    session.flush = AsyncMock()
    svc = object.__new__(PaymentService)
    svc._payment_repo = MagicMock()
    svc._payment_repo.page_for_admin = AsyncMock(return_value=([(_payment(), "VP-1")], 11, "amountMinor asc"))

    page = await svc.page_for_admin(page=1, page_size=10, query=None, status=None, order_by="amountMinor asc")

    assert [r.vid for r in page.items] == ["VP-1"]
    assert page.meta.total == 11
    assert page.meta.sort == "amountMinor asc"
    assert page.meta.sortable_fields == ["amountMinor", "dateCreated", "provider", "status", "txRef"]
    svc._payment_repo.page_for_admin.assert_awaited_once_with(1, 10, None, None, "amountMinor asc")

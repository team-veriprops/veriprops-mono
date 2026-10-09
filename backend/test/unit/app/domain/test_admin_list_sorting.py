"""Every admin DataTable list sorts server-side, across pages, on its own allowlist.

Each case drives one list repo with a client sort and with a sort outside its allowlist, and
reads the ORDER BY it sends: an allowed column is honoured (with the id tiebreaker that keeps
OFFSET pages stable), anything else falls back to the list's default and reports it.
"""
from typing import Any, Callable
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.domain.audit.models import AuditLog, QueryAuditLogDto
from main.app.domain.audit.repo import AuditLogRepo
from main.app.domain.compliance.erasure.models import DataErasureRequest, QueryDataErasureRequestDto
from main.app.domain.compliance.erasure.repo import DataErasureRequestRepo
from main.app.domain.payment.refund_request.models import QueryRefundRequestDto, RefundRequest, RefundRequestStatus
from main.app.domain.payment.refund_request.repo import RefundRequestRepo
from main.app.domain.user.agent.profile.models import AgentProfile, QueryAgentProfileDto
from main.app.domain.user.agent.profile.repo import AgentProfileRepo
from main.app.domain.user.models import QueryUserDto, User
from main.app.domain.user.repo import UserRepo
from main.app.domain.verification.models import QueryVerificationDto, Verification
from main.app.domain.verification.repo import VerificationRepo
from main.appodus_utils.db.db_utils import DbUtils
from main.appodus_utils.db.session import db_session_ctx


@pytest.fixture
def session():
    session = MagicMock()
    result = MagicMock()
    result.all.return_value = []
    result.scalars.return_value.all.return_value = []
    session.scalar = AsyncMock(return_value=0)
    session.execute = AsyncMock(return_value=result)
    token = db_session_ctx.set(session)
    yield session
    db_session_ctx.reset(token)


def _repo(cls, model, query_dto):
    repo = object.__new__(cls)
    repo._model = model
    repo._db_utils = DbUtils(model=model, query_qto=query_dto)
    return repo


def _order_by(session) -> str:
    sql = " ".join(str(session.execute.await_args.args[0].compile()).lower().split())
    return sql.split(" order by ", 1)[1].split(" limit ", 1)[0]


# (name, repo factory, call(repo, order_by), allowed sort, its ORDER BY, default sort, its ORDER BY)
Case = tuple[str, Callable[[], Any], Callable[[Any, Any], Any], str, str, str, str]
CASES: list[Case] = [
    ("admin team", lambda: _repo(UserRepo, User, QueryUserDto),
     lambda r, o: r.page_admins(offset=0, limit=10, order_by=o),
     "email desc", "users.email desc, users.id asc", "firstName asc", "users.first_name asc, users.id asc"),
    ("users directory", lambda: _repo(UserRepo, User, QueryUserDto),
     lambda r, o: r.page_users(offset=0, limit=10, order_by=o),
     "trustStatus asc", "users.trust_status asc, users.id asc",
     "dateCreated desc", "users.date_created desc, users.id asc"),
    ("refund queue", lambda: _repo(RefundRequestRepo, RefundRequest, QueryRefundRequestDto),
     lambda r, o: r.page_with_vid(0, 10, RefundRequestStatus.PENDING, o),
     "amountMinor desc", "refund_requests.amount_minor desc, refund_requests.id asc",
     "dateCreated asc", "refund_requests.date_created asc, refund_requests.id asc"),
    ("refund record", lambda: _repo(RefundRequestRepo, RefundRequest, QueryRefundRequestDto),
     lambda r, o: r.page_with_vid(0, 10, None, o),
     "status asc", "refund_requests.status asc, refund_requests.id asc",
     "dateCreated desc", "refund_requests.date_created desc, refund_requests.id asc"),
    ("erasure requests", lambda: _repo(DataErasureRequestRepo, DataErasureRequest, QueryDataErasureRequestDto),
     lambda r, o: r.page_by_status(None, 0, 10, o),
     "slaDueAt asc", "data_erasure_requests.sla_due_at asc, data_erasure_requests.id asc",
     "dateCreated desc", "data_erasure_requests.date_created desc, data_erasure_requests.id asc"),
    ("agent applications", lambda: _repo(AgentProfileRepo, AgentProfile, QueryAgentProfileDto),
     lambda r, o: r.page_applications(None, 0, 10, order_by=o),
     "status asc", "agent_profiles.status asc, agent_profiles.id asc",
     "submittedAt desc", "agent_profiles.submitted_at desc, agent_profiles.id asc"),
    ("verifications", lambda: _repo(VerificationRepo, Verification, QueryVerificationDto),
     lambda r, o: r.page_admin(order_by=o),
     "slaDueDate asc", "verifications.sla_due_date asc, verifications.id asc",
     "dateCreated desc", "verifications.date_created desc, verifications.id asc"),
    ("admin actions", lambda: _repo(AuditLogRepo, AuditLog, QueryAuditLogDto),
     lambda r, o: r.list_admin_actions(["X"], None, None, 0, 10, o),
     "resourceType asc", "audit_logs.resource_type asc, audit_logs.id asc",
     "occurredAt desc", "audit_logs.occurred_at desc, audit_logs.id asc"),
]


@pytest.mark.parametrize("name,make,call,allowed,allowed_sql,default,default_sql", CASES, ids=[c[0] for c in CASES])
class TestAdminListSorting:
    async def test_an_allowed_sort_is_applied_and_reported(
        self, session, name, make, call, allowed, allowed_sql, default, default_sql,
    ):
        *_, applied = await call(make(), allowed)
        assert applied == allowed
        assert _order_by(session) == allowed_sql

    async def test_no_sort_or_a_disallowed_sort_falls_back_to_the_default(
        self, session, name, make, call, allowed, allowed_sql, default, default_sql,
    ):
        for raw in (None, "deleted asc", "email asc, status desc"):
            if raw and raw.split(" ")[0] == allowed.split(" ")[0]:
                continue
            *_, applied = await call(make(), raw)
            assert applied == default, raw
            assert _order_by(session) == default_sql, raw

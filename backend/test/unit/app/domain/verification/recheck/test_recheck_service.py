"""RecheckService (§14.1): request guards, admin approve issues a charge + scopes, payment
confirmation reopens the scoped tasks and records the v2.0 version bump."""
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.core.state.status import AgentRole, ReportRevisionKind, VerificationStatus, VerificationTier
from main.app.domain.verification.recheck.models import (
    DecideRecheckDto,
    RecheckStatus,
    RequestRecheckDto,
)
from main.app.domain.verification.recheck.service import RecheckService
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.exception.exceptions import (
    InvalidResourceStateException,
    ValidationException,
)


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


def _verification(status=VerificationStatus.COMPLETED):
    return SimpleNamespace(id="v-1", vid="VP-1", tier=VerificationTier.STANDARD.value,
                           status=status.value, customer_id="cust-1")


def _recheck(status=RecheckStatus.PENDING, scope=None, payment_id=None):
    return SimpleNamespace(
        id="rc-1", verification_id="v-1", customer_id="cust-1", reason="wrong survey",
        documents=None, scope_roles=scope, status=status.value, price_minor=3_600_000,
        payment_id=payment_id, decision_note=None,
    )


def _service(verification=None, recheck=None):
    svc = object.__new__(RecheckService)
    svc._repo = MagicMock()
    svc._verifications = MagicMock()
    svc._verification_repo = MagicMock()
    svc._reviews = MagicMock()
    svc._payments = MagicMock()
    svc._config = MagicMock()
    svc._audit = MagicMock()
    svc._audit.schedule = MagicMock()

    v = verification if verification is not None else _verification()
    svc._verifications.get_owned = AsyncMock(return_value=v)
    svc._config.get_int = AsyncMock(return_value=30)
    svc._repo.create_return_model = AsyncMock(return_value=_recheck())
    svc._repo.get_model = AsyncMock(return_value=recheck or _recheck())
    svc._repo.get_by_payment = AsyncMock(return_value=recheck)
    svc._repo.update = AsyncMock()
    svc._verification_repo.update = AsyncMock()
    svc._payments.initiate_secondary = AsyncMock(return_value=SimpleNamespace(id="pay-1", checkout_url="/pay"))
    svc._reviews.reopen_task = AsyncMock()
    return svc


class TestRequest:
    async def test_request_on_completed_creates_pending(self):
        svc = _service()
        await svc.request("v-1", "cust-1", RequestRecheckDto(reason="wrong survey plan attached"))
        dto = svc._repo.create_return_model.await_args.args[0]
        assert dto.status == RecheckStatus.PENDING
        assert dto.price_minor == 3_600_000  # 30% of STANDARD

    async def test_request_blocked_when_not_completed(self):
        svc = _service(verification=_verification(status=VerificationStatus.IN_PROGRESS))
        with pytest.raises(InvalidResourceStateException):
            await svc.request("v-1", "cust-1", RequestRecheckDto(reason="x"))

    async def test_request_requires_reason(self):
        svc = _service()
        with pytest.raises(ValidationException):
            await svc.request("v-1", "cust-1", RequestRecheckDto(reason="   "))


class TestDecide:
    async def test_reject_sets_rejected(self, monkeypatch):
        import main.app.domain.verification.recheck.service as mod
        monkeypatch.setattr(mod, "publish_domain_event", AsyncMock())
        svc = _service(recheck=_recheck())
        await svc.admin_decide("rc-1", DecideRecheckDto(approve=False, note="unfounded"), "admin-1")
        dto = svc._repo.update.await_args.args[1]
        assert dto.status == RecheckStatus.REJECTED.value

    async def test_approve_scopes_and_charges(self, monkeypatch):
        import main.app.domain.verification.recheck.service as mod
        monkeypatch.setattr(mod, "publish_domain_event", AsyncMock())
        svc = _service(recheck=_recheck())
        await svc.admin_decide(
            "rc-1", DecideRecheckDto(approve=True, scope_roles=[AgentRole.SURVEYOR]), "admin-1"
        )
        svc._payments.initiate_secondary.assert_awaited_once()
        dto = svc._repo.update.await_args.args[1]
        assert dto.status == RecheckStatus.APPROVED.value
        assert dto.scope_roles == [AgentRole.SURVEYOR.value]

    async def test_approve_requires_scope(self, monkeypatch):
        import main.app.domain.verification.recheck.service as mod
        monkeypatch.setattr(mod, "publish_domain_event", AsyncMock())
        svc = _service(recheck=_recheck())
        with pytest.raises(ValidationException):
            await svc.admin_decide("rc-1", DecideRecheckDto(approve=True, scope_roles=[]), "admin-1")


class TestOnPaymentConfirmed:
    async def test_reopens_scope_and_marks_recheck_version(self):
        recheck = _recheck(status=RecheckStatus.APPROVED, scope=[AgentRole.SURVEYOR.value], payment_id="pay-1")
        svc = _service(recheck=recheck)
        await svc.on_payment_confirmed("pay-1")
        # pending_revision_kind set to RECHECK so the next release is v2.0
        upd = svc._verification_repo.update.await_args.args[1]
        assert upd.pending_revision_kind == ReportRevisionKind.RECHECK.value
        svc._reviews.reopen_task.assert_awaited_once()
        assert svc._reviews.reopen_task.await_args.args[1] == AgentRole.SURVEYOR

    async def test_idempotent_when_not_approved(self):
        recheck = _recheck(status=RecheckStatus.STARTED, payment_id="pay-1")
        svc = _service(recheck=recheck)
        await svc.on_payment_confirmed("pay-1")
        svc._reviews.reopen_task.assert_not_called()

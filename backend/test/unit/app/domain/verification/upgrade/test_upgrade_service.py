"""UpgradeService (§14.2): tier-delta pricing, idempotent resubmit, and applying the upgrade
on payment (tier raised, new tasks added, SLA extended, report bumps to v3.0)."""
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.core.state.status import ReportRevisionKind, VerificationStatus, VerificationTier
from main.app.domain.verification.upgrade.models import RequestUpgradeDto, UpgradeStatus
from main.app.domain.verification.pricing import TIER_PRICE_NGN_KOBO
from main.app.domain.verification.upgrade.service import UpgradeService
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


def _verification(status=VerificationStatus.COMPLETED, tier=VerificationTier.STANDARD):
    return SimpleNamespace(id="v-1", vid="VP-1", tier=tier.value, status=status.value,
                           customer_id="cust-1", sla_due_date=None)


def _upgrade(status=UpgradeStatus.PENDING, to=VerificationTier.PREMIUM, payment_id="pay-1"):
    return SimpleNamespace(
        id="up-1", verification_id="v-1", customer_id="cust-1",
        from_tier=VerificationTier.STANDARD.value, to_tier=to.value, delta_minor=18_000_000,
        status=status.value, payment_id=payment_id, idempotency_key="v-1:PREMIUM",
    )


def _service(verification=None, existing_key=None, upgrade=None):
    svc = object.__new__(UpgradeService)
    svc._repo = MagicMock()
    svc._verifications = MagicMock()
    svc._verification_repo = MagicMock()
    svc._tasks = MagicMock()
    svc._payments = MagicMock()
    svc._pricing = MagicMock()
    svc._audit = MagicMock()
    svc._audit.schedule = MagicMock()

    v = verification if verification is not None else _verification()
    svc._verifications.get_owned = AsyncMock(return_value=v)
    svc._pricing.tier_price_kobo = AsyncMock(side_effect=lambda tier: TIER_PRICE_NGN_KOBO[tier])
    svc._repo.get_by_key = AsyncMock(return_value=existing_key)
    svc._repo.get_by_payment = AsyncMock(return_value=upgrade)
    svc._repo.create_return_model = AsyncMock(return_value=_upgrade())
    svc._repo.get_model = AsyncMock(return_value=upgrade or _upgrade())
    svc._repo.update = AsyncMock()
    svc._verification_repo.update = AsyncMock()
    svc._verification_repo.get_model = AsyncMock(return_value=v)
    svc._payments.initiate_secondary = AsyncMock(return_value=SimpleNamespace(id="pay-1", checkout_url="/pay"))
    svc._tasks.prepare_for_paid = AsyncMock()
    return svc


class TestRequest:
    async def test_request_charges_the_delta(self):
        svc = _service()
        await svc.request("v-1", "cust-1", RequestUpgradeDto(to_tier=VerificationTier.PREMIUM))
        svc._payments.initiate_secondary.assert_awaited_once()
        amount = svc._payments.initiate_secondary.await_args.kwargs["amount_minor"]
        assert amount == 30_000_000 - 12_000_000  # PREMIUM − STANDARD

    async def test_rejects_non_upgrade(self):
        svc = _service()
        with pytest.raises(ValidationException):
            await svc.request("v-1", "cust-1", RequestUpgradeDto(to_tier=VerificationTier.BASIC))

    async def test_blocked_on_terminal_state(self):
        svc = _service(verification=_verification(status=VerificationStatus.REFUNDED))
        with pytest.raises(InvalidResourceStateException):
            await svc.request("v-1", "cust-1", RequestUpgradeDto(to_tier=VerificationTier.PREMIUM))

    async def test_idempotent_resubmit_reuses_pending(self):
        existing = _upgrade(status=UpgradeStatus.PENDING)
        svc = _service(existing_key=existing)
        out = await svc.request("v-1", "cust-1", RequestUpgradeDto(to_tier=VerificationTier.PREMIUM))
        assert out is existing
        svc._payments.initiate_secondary.assert_not_called()  # no double charge


class TestOnPaymentConfirmed:
    async def test_applies_upgrade_from_completed(self):
        v = _verification(status=VerificationStatus.COMPLETED)
        svc = _service(verification=v, upgrade=_upgrade(status=UpgradeStatus.PENDING))
        await svc.on_payment_confirmed("pay-1")
        upd = svc._verification_repo.update.await_args.args[1]
        assert upd.tier == VerificationTier.PREMIUM.value
        assert upd.status == VerificationStatus.IN_PROGRESS.value
        assert upd.pending_revision_kind == ReportRevisionKind.TIER_UPGRADE.value
        svc._tasks.prepare_for_paid.assert_awaited_once()  # new scope's tasks instantiated
        assert v.sla_due_date is not None  # SLA extended

    async def test_idempotent_when_not_pending(self):
        svc = _service(upgrade=_upgrade(status=UpgradeStatus.PAID))
        await svc.on_payment_confirmed("pay-1")
        svc._tasks.prepare_for_paid.assert_not_called()

"""PaymentService (PRD §4.4, §4.6, §5.4) — repos mocked, no DB.

Covers the phone gate, initiation idempotency, and the idempotent webhook that
drives PAID exactly once + upgrades the customer to trusted.
"""
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.core.idempotency.service import IdempotencyOutcome
from main.app.core.state.status import VerificationStatus
from main.app.domain.audit.models import AuditActionType
from main.app.domain.payment.models import (
    PaymentMethodKind,
    PaymentStatus,
    PaymentWebhookDto,
)
from main.app.domain.payment.service import PaymentService
from main.app.domain.user.auth.session.models import UserPersona
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.exception.exceptions import ValidationException


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


def _verification(**over):
    base = dict(
        id="ver-1", vid="VP-2026-ABC123", status=VerificationStatus.SUBMITTED.value,
        price_locked_minor=12_000_000, currency="NGN", charge_currency="NGN",
        charge_amount_minor=12_000_000,
    )
    base.update(over)
    return SimpleNamespace(**base)


def _make_service(phone_verified=True, verification=None):
    svc = object.__new__(PaymentService)
    svc._repo = MagicMock()
    svc._verification_service = MagicMock()
    svc._task_service = MagicMock()
    svc._user_service = MagicMock()
    svc._idempotency = MagicMock()
    svc._audit = MagicMock()

    svc._verification_service.get_owned = AsyncMock(return_value=verification or _verification())
    svc._verification_service.mark_payment_pending = AsyncMock()
    svc._verification_service.mark_paid = AsyncMock()
    # At PAID the payment service instantiates/broadcasts tasks (§6.2).
    svc._task_service.prepare_for_paid = AsyncMock()
    svc._user_service.get_user_model = AsyncMock(
        return_value=SimpleNamespace(phone_verified=phone_verified)
    )
    svc._user_service.upgrade_trust_status_if_eligible = AsyncMock()
    svc._repo.create_return_model = AsyncMock(return_value=SimpleNamespace(id="pay-1", tx_ref="VP-2026-ABC123-xyz"))
    svc._repo.update = AsyncMock()
    return svc


class TestInitiate:
    async def test_blocks_when_phone_unverified(self):
        svc = _make_service(phone_verified=False)
        with pytest.raises(ValidationException):
            await svc.initiate("ver-1", "cust-1", PaymentMethodKind.CARD)

    async def test_creates_payment_and_moves_to_pending(self):
        svc = _make_service()
        await svc.initiate("ver-1", "cust-1", PaymentMethodKind.CARD)
        svc._repo.create_return_model.assert_awaited_once()
        svc._verification_service.mark_payment_pending.assert_awaited_once_with("ver-1")
        assert svc._audit.schedule.call_args.kwargs["action"] == AuditActionType.PAYMENT_INITIATED

    async def test_replays_on_double_tap(self):
        svc = _make_service()
        svc._idempotency.begin_or_replay = AsyncMock(
            return_value=IdempotencyOutcome(is_replay=True, resource_id="pay-1")
        )
        svc._repo.get_model = AsyncMock(return_value=SimpleNamespace(id="pay-1"))
        await svc.initiate("ver-1", "cust-1", PaymentMethodKind.CARD, idempotency_key="k-1")
        svc._repo.create_return_model.assert_not_called()


class TestWebhook:
    async def test_success_marks_paid_and_upgrades_trust(self):
        svc = _make_service()
        svc._idempotency.claim = AsyncMock(return_value=True)
        svc._repo.get_by_tx_ref = AsyncMock(
            return_value=SimpleNamespace(id="pay-1", verification_id="ver-1", customer_id="cust-1", failure_count=0)
        )
        processed = await svc.handle_webhook(
            PaymentWebhookDto(event_id="evt-1", tx_ref="VP-2026-ABC123-xyz", succeeded=True)
        )
        assert processed is True
        svc._verification_service.mark_paid.assert_awaited_once_with("ver-1")
        svc._user_service.upgrade_trust_status_if_eligible.assert_awaited_once_with("cust-1", UserPersona.CUSTOMER)

    async def test_duplicate_webhook_is_noop(self):
        svc = _make_service()
        svc._idempotency.claim = AsyncMock(return_value=False)  # already seen
        processed = await svc.handle_webhook(
            PaymentWebhookDto(event_id="evt-1", tx_ref="VP-2026-ABC123-xyz", succeeded=True)
        )
        assert processed is False
        svc._verification_service.mark_paid.assert_not_called()

    async def test_failed_webhook_marks_failed(self):
        svc = _make_service()
        svc._idempotency.claim = AsyncMock(return_value=True)
        svc._repo.get_by_tx_ref = AsyncMock(
            return_value=SimpleNamespace(id="pay-1", verification_id="ver-1", customer_id="cust-1", failure_count=0)
        )
        await svc.handle_webhook(
            PaymentWebhookDto(event_id="evt-1", tx_ref="VP-2026-ABC123-xyz", succeeded=False)
        )
        # last update sets FAILED
        statuses = [c.args[1].status for c in svc._repo.update.call_args_list if c.args[1].status]
        assert PaymentStatus.FAILED.value in statuses
        svc._verification_service.mark_paid.assert_not_called()

"""VerificationService (PRD §5, §4.4) — repos mocked, no DB.

Covers the DRAFT → SUBMITTED transition (property + price-lock + consent), the
idempotent draft create (double-tap), and the payment-driven PAID transition with
its idempotency + state-machine guards.
"""
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.core.idempotency.service import IdempotencyOutcome
from main.app.core.state.status import VerificationStatus, VerificationTier
from main.app.domain.audit.models import AuditActionType
from main.app.domain.property.models import PropertyInputDto, PropertyType
from main.app.domain.user.auth.consent.models import ConsentDocumentType
from main.app.domain.verification.models import (
    SubmitVerificationDto,
    VerificationConsentDto,
)
from main.app.domain.verification.service import VerificationService
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.db.types.money import TransactionCurrency
from main.appodus_utils.exception.exceptions import IllegalStateTransitionException


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
        id="ver-1", vid="VP-2026-ABC123", customer_id="cust-1", property_id=None,
        tier=None, status=VerificationStatus.DRAFT.value, price_locked_minor=None,
        currency="NGN", charge_currency=None, charge_amount_minor=None,
        price_lock_expires_at=None, paid_at=None, sla_due_date=None, draft_step=0,
        draft_payload=None,
    )
    base.update(over)
    return SimpleNamespace(**base)


def _make_service():
    svc = object.__new__(VerificationService)
    svc._repo = MagicMock()
    svc._property_service = MagicMock()
    svc._consent_service = MagicMock()
    svc._idempotency = MagicMock()
    svc._audit = MagicMock()
    svc._repo.create_return_model = AsyncMock(return_value=_verification())
    svc._repo.update = AsyncMock()
    svc._property_service.create = AsyncMock(return_value=SimpleNamespace(id="prop-1"))
    svc._consent_service.record_user_consent = AsyncMock()
    return svc


def _submit_dto():
    return SubmitVerificationDto(
        property=PropertyInputDto(property_type=PropertyType.LAND, address="Lekki", landmark="near junction"),
        tier=VerificationTier.STANDARD,
        currency=TransactionCurrency.NGN,
        consent=VerificationConsentDto(consent_version="1.0.0"),
    )


class TestCreateDraft:
    async def test_creates_when_no_idempotency_key(self):
        svc = _make_service()
        await svc.create_draft("cust-1")
        svc._repo.create_return_model.assert_awaited_once()

    async def test_replays_existing_on_double_tap(self):
        svc = _make_service()
        svc._idempotency.begin_or_replay = AsyncMock(
            return_value=IdempotencyOutcome(is_replay=True, resource_id="ver-1")
        )
        svc._repo.get_model = AsyncMock(return_value=_verification())
        result = await svc.create_draft("cust-1", idempotency_key="k-1")
        assert result.id == "ver-1"
        svc._repo.create_return_model.assert_not_called()

    async def test_fresh_key_creates_and_completes(self):
        svc = _make_service()
        svc._idempotency.begin_or_replay = AsyncMock(return_value=IdempotencyOutcome(is_replay=False))
        svc._idempotency.complete = AsyncMock()
        await svc.create_draft("cust-1", idempotency_key="k-1")
        svc._repo.create_return_model.assert_awaited_once()
        svc._idempotency.complete.assert_awaited_once()


class TestSubmit:
    async def test_draft_to_submitted_with_property_and_consent(self):
        svc = _make_service()
        svc._repo.get_model = AsyncMock(return_value=_verification())
        await svc.submit("ver-1", "cust-1", _submit_dto(), ip_address="1.2.3.4")

        svc._property_service.create.assert_awaited_once()
        # VERIFICATION_TERMS recorded.
        assert svc._consent_service.record_user_consent.call_args.kwargs["document_type"] == (
            ConsentDocumentType.VERIFICATION_TERMS
        )
        # Status transition persisted + audited.
        update_dto = svc._repo.update.call_args_list[0].args[1]
        assert update_dto.status == VerificationStatus.SUBMITTED.value
        assert update_dto.price_locked_minor and update_dto.price_locked_minor > 0
        assert svc._audit.schedule.call_args.kwargs["action"] == AuditActionType.VERIFICATION_SUBMITTED

    async def test_rejects_submit_from_paid(self):
        svc = _make_service()
        svc._repo.get_model = AsyncMock(return_value=_verification(status=VerificationStatus.PAID.value))
        with pytest.raises(IllegalStateTransitionException):
            await svc.submit("ver-1", "cust-1", _submit_dto())


class TestMarkPaid:
    async def test_payment_pending_to_paid(self):
        svc = _make_service()
        svc._repo.get_model = AsyncMock(
            return_value=_verification(status=VerificationStatus.PAYMENT_PENDING.value, tier="STANDARD")
        )
        await svc.mark_paid("ver-1")
        update_dto = svc._repo.update.call_args_list[0].args[1]
        assert update_dto.status == VerificationStatus.PAID.value

    async def test_idempotent_when_already_paid(self):
        svc = _make_service()
        svc._repo.get_model = AsyncMock(return_value=_verification(status=VerificationStatus.PAID.value))
        await svc.mark_paid("ver-1")
        svc._repo.update.assert_not_called()

    async def test_rejects_paid_from_draft(self):
        svc = _make_service()
        svc._repo.get_model = AsyncMock(return_value=_verification(status=VerificationStatus.DRAFT.value))
        with pytest.raises(IllegalStateTransitionException):
            await svc.mark_paid("ver-1")

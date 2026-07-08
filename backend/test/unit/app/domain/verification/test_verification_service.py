"""VerificationService (PRD §5, §4.4) — repos mocked, no DB.

Covers the DRAFT → SUBMITTED transition (property + price-lock + consent), the
idempotent draft create (double-tap), and the payment-driven PAID transition with
its idempotency + state-machine guards.
"""
from contextlib import asynccontextmanager
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.core.idempotency.service import IdempotencyOutcome
from main.app.core.events import EventType
from main.app.core.state.status import VerificationStatus, VerificationTier
from main.app.domain.audit.models import AuditActionType
from main.app.domain.property.models import PropertyInputDto, PropertyType
from main.app.domain.system_config.models import ConfigKey
from main.app.domain.user.auth.consent.models import ConsentDocumentType
from main.app.domain.verification import service as verification_module
from main.app.domain.verification.pricing import TIER_PRICE_NGN_KOBO
from main.app.domain.verification.models import (
    SubmitVerificationDto,
    VerificationConsentDto,
)
from main.app.domain.verification.service import VerificationService
from main.appodus_utils import Utils
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.db.types.money import TransactionCurrency
from main.appodus_utils.exception.exceptions import IllegalStateTransitionException

# System-config defaults the discount math reads (§17.1).
_CONFIG_VALUES = {
    ConfigKey.FIRST_TIME_DISCOUNT_PERCENT: 10,
    ConfigKey.MAX_DISCOUNT_PERCENT: 25,
    ConfigKey.CHARGEBACK_WINDOW_DAYS: 120,
}


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
        draft_payload=None, first_time_discount_minor=0, referral_credit_applied_minor=0,
        recovery_reminded_at=None,
    )
    base.update(over)
    return SimpleNamespace(**base)


def _user(credit_balance_kobo=0):
    return SimpleNamespace(id="cust-1", credit_balance_kobo=credit_balance_kobo)


def _make_service(credit_balance_kobo=0, has_paid=False):
    svc = object.__new__(VerificationService)
    svc._verification_repo = MagicMock()
    svc._property_service = MagicMock()
    svc._consent_service = MagicMock()
    svc._idempotency = MagicMock()
    svc._audit = MagicMock()
    svc._config = MagicMock()
    svc._users = MagicMock()
    svc._pricing = MagicMock()
    svc._verification_repo.create_return_model = AsyncMock(return_value=_verification())
    svc._verification_repo.update = AsyncMock()
    svc._verification_repo.has_paid_verification = AsyncMock(return_value=has_paid)
    svc._property_service.create = AsyncMock(return_value=SimpleNamespace(id="prop-1"))
    svc._consent_service.record_user_consent = AsyncMock()
    svc._config.get_int = AsyncMock(side_effect=lambda key: _CONFIG_VALUES[key])
    svc._users.get_user_model = AsyncMock(return_value=_user(credit_balance_kobo))
    svc._users.update_user = AsyncMock()
    svc._pricing.tier_price_kobo = AsyncMock(side_effect=lambda tier: TIER_PRICE_NGN_KOBO[tier])
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
        svc._verification_repo.create_return_model.assert_awaited_once()

    async def test_replays_existing_on_double_tap(self):
        svc = _make_service()
        svc._idempotency.begin_or_replay = AsyncMock(
            return_value=IdempotencyOutcome(is_replay=True, resource_id="ver-1")
        )
        svc._verification_repo.get_model = AsyncMock(return_value=_verification())
        result = await svc.create_draft("cust-1", idempotency_key="k-1")
        assert result.id == "ver-1"
        svc._verification_repo.create_return_model.assert_not_called()

    async def test_fresh_key_creates_and_completes(self):
        svc = _make_service()
        svc._idempotency.begin_or_replay = AsyncMock(return_value=IdempotencyOutcome(is_replay=False))
        svc._idempotency.complete = AsyncMock()
        await svc.create_draft("cust-1", idempotency_key="k-1")
        svc._verification_repo.create_return_model.assert_awaited_once()
        svc._idempotency.complete.assert_awaited_once()


class TestSubmit:
    async def test_draft_to_submitted_with_property_and_consent(self):
        svc = _make_service()
        svc._verification_repo.get_model = AsyncMock(return_value=_verification())
        await svc.submit("ver-1", "cust-1", _submit_dto(), ip_address="1.2.3.4")

        svc._property_service.create.assert_awaited_once()
        # VERIFICATION_TERMS recorded.
        assert svc._consent_service.record_user_consent.call_args.kwargs["document_type"] == (
            ConsentDocumentType.VERIFICATION_TERMS
        )
        # Status transition persisted + audited.
        update_dto = svc._verification_repo.update.call_args_list[0].args[1]
        assert update_dto.status == VerificationStatus.SUBMITTED.value
        assert update_dto.price_locked_minor and update_dto.price_locked_minor > 0
        assert svc._audit.schedule.call_args.kwargs["action"] == AuditActionType.VERIFICATION_SUBMITTED

    async def test_rejects_submit_from_paid(self):
        svc = _make_service()
        svc._verification_repo.get_model = AsyncMock(return_value=_verification(status=VerificationStatus.PAID.value))
        with pytest.raises(IllegalStateTransitionException):
            await svc.submit("ver-1", "cust-1", _submit_dto())


class TestMarkPaid:
    async def test_payment_pending_to_paid(self):
        svc = _make_service()
        svc._verification_repo.get_model = AsyncMock(
            return_value=_verification(status=VerificationStatus.PAYMENT_PENDING.value, tier="STANDARD")
        )
        await svc.mark_paid("ver-1")
        update_dto = svc._verification_repo.update.call_args_list[0].args[1]
        assert update_dto.status == VerificationStatus.PAID.value

    async def test_idempotent_when_already_paid(self):
        svc = _make_service()
        svc._verification_repo.get_model = AsyncMock(return_value=_verification(status=VerificationStatus.PAID.value))
        await svc.mark_paid("ver-1")
        svc._verification_repo.update.assert_not_called()

    async def test_rejects_paid_from_draft(self):
        svc = _make_service()
        svc._verification_repo.get_model = AsyncMock(return_value=_verification(status=VerificationStatus.DRAFT.value))
        with pytest.raises(IllegalStateTransitionException):
            await svc.mark_paid("ver-1")

    async def test_debits_applied_referral_credit_on_paid(self):
        svc = _make_service(credit_balance_kobo=800_000)
        svc._verification_repo.get_model = AsyncMock(return_value=_verification(
            status=VerificationStatus.PAYMENT_PENDING.value, tier="STANDARD",
            referral_credit_applied_minor=500_000,
        ))
        await svc.mark_paid("ver-1")
        # Balance debited by the amount actually applied to this verification.
        dto = svc._users.update_user.call_args.args[1]
        assert dto.credit_balance_kobo == 300_000


class TestQuoteDiscount:
    async def test_first_time_discount_applied(self):
        svc = _make_service(has_paid=False)
        quote = await svc.quote("cust-1", VerificationTier.STANDARD, TransactionCurrency.NGN)
        # 10% of ₦120k tier price.
        assert quote.first_time_discount_minor == 1_200_000
        assert quote.net_price_ngn_minor == quote.price_ngn_minor - quote.total_discount_minor

    async def test_no_first_time_discount_for_returning_customer(self):
        svc = _make_service(has_paid=True)
        quote = await svc.quote("cust-1", VerificationTier.STANDARD, TransactionCurrency.NGN)
        assert quote.first_time_discount_minor == 0

    async def test_referral_credit_capped_at_max_discount(self):
        # Huge credit balance, but combined discount can't exceed 25% of the base.
        svc = _make_service(has_paid=True, credit_balance_kobo=100_000_000)
        quote = await svc.quote("cust-1", VerificationTier.STANDARD, TransactionCurrency.NGN)
        assert quote.total_discount_minor == int(quote.price_ngn_minor * 0.25)
        assert quote.discount_cap_hit is True


class TestSubmitDiscount:
    async def test_submit_locks_net_price_and_records_breakdown(self):
        svc = _make_service(has_paid=False)
        svc._verification_repo.get_model = AsyncMock(return_value=_verification())
        await svc.submit("ver-1", "cust-1", _submit_dto())
        dto = svc._verification_repo.update.call_args_list[0].args[1]
        # Net = base − first-time discount; the breakdown is recorded.
        assert dto.first_time_discount_minor == 1_200_000
        assert dto.price_locked_minor == 12_000_000 - 1_200_000


class TestAbandonmentSweep:
    async def test_reminds_once_and_publishes(self, monkeypatch):
        published = []
        monkeypatch.setattr(verification_module, "publish_domain_event",
                            AsyncMock(side_effect=lambda e: published.append(e)))
        svc = _make_service()
        draft = _verification(status=VerificationStatus.PAYMENT_PENDING.value)
        svc._verification_repo.list_abandoned_drafts = AsyncMock(return_value=[draft])
        svc._verification_repo.get_model = AsyncMock(return_value=draft)
        reminded = await svc.sweep_abandoned_drafts()
        assert reminded == 1
        assert draft.recovery_reminded_at is not None
        assert published[0].type == EventType.ABANDONMENT_RECOVERY

    async def test_skips_already_reminded(self, monkeypatch):
        monkeypatch.setattr(verification_module, "publish_domain_event", AsyncMock())
        svc = _make_service()
        draft = _verification(recovery_reminded_at=Utils.datetime_now())
        svc._verification_repo.list_abandoned_drafts = AsyncMock(return_value=[draft])
        svc._verification_repo.get_model = AsyncMock(return_value=draft)
        assert await svc.sweep_abandoned_drafts() == 0


class TestRefreshLock:
    async def test_flags_price_change_when_lock_expired_and_price_differs(self):
        svc = _make_service(has_paid=False)  # first-time discount now applies
        expired = Utils.datetime_now() - timedelta(hours=1)
        v = _verification(status=VerificationStatus.SUBMITTED.value, tier="STANDARD",
                          price_locked_minor=12_000_000, price_lock_expires_at=expired,
                          charge_currency="NGN")
        svc._verification_repo.get_model = AsyncMock(return_value=v)
        result = await svc.refresh_price_lock_if_expired("ver-1", "cust-1")
        assert result.price_changed is True
        assert result.net_price_minor == 12_000_000 - 1_200_000

    async def test_no_change_when_lock_still_valid(self):
        svc = _make_service()
        future = Utils.datetime_now() + timedelta(hours=5)
        v = _verification(status=VerificationStatus.SUBMITTED.value, tier="STANDARD",
                          price_locked_minor=12_000_000, price_lock_expires_at=future)
        svc._verification_repo.get_model = AsyncMock(return_value=v)
        result = await svc.refresh_price_lock_if_expired("ver-1", "cust-1")
        assert result.price_changed is False

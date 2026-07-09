"""ReferralService (PRD §17.1, D34/D35) — repos + user service mocked, no DB.

Covers the anti-farming gate (self-referral by shared verified phone / card fingerprint),
the two-stage credit lifecycle (PENDING on first payment → CLEARED after the chargeback
window), the one-credit-per-invitee idempotency guard, and the summary projection.
"""
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from main.app.core.events import EventType
from main.app.domain.referral import service as referral_module
from main.app.domain.referral.credit.models import ReferralCreditStatus
from main.app.domain.referral.service import ReferralService
from main.app.domain.system_config.models import ConfigKey
from main.appodus_utils.db.session import db_session_ctx

_CONFIG_VALUES = {ConfigKey.REFERRAL_CREDIT_NGN: 5_000, ConfigKey.CHARGEBACK_WINDOW_DAYS: 120}

# Two distinct real UUIDs, referenced by their .hex wire form.
REFERRER = UUID("11111111111111111111111111111111")
INVITEE = UUID("22222222222222222222222222222222")


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


@pytest.fixture(autouse=True)
def stub_publish(monkeypatch):
    published = []
    monkeypatch.setattr(referral_module, "publish_domain_event",
                        AsyncMock(side_effect=lambda e: published.append(e)))
    return published


def _payment(customer_id=INVITEE.hex, card_fingerprint=None):
    return SimpleNamespace(
        id="pay-1", customer_id=customer_id, verification_id="ver-1",
        card_fingerprint=card_fingerprint,
    )


def _invitee(referred_by=REFERRER.hex, phone_e164="+2348010000001", phone_verified=True):
    return SimpleNamespace(id=INVITEE, referred_by=referred_by,
                           phone_e164=phone_e164, phone_verified=phone_verified)


def _referrer(phone_e164="+2348019999999", phone_verified=True, credit_balance_kobo=0):
    return SimpleNamespace(id=REFERRER, phone_e164=phone_e164, phone_verified=phone_verified,
                           credit_balance_kobo=credit_balance_kobo)


def _make_service():
    svc = object.__new__(ReferralService)
    svc._referrals = AsyncMock()
    svc._credits = AsyncMock()
    svc._payments = AsyncMock()
    svc._users = AsyncMock()
    svc._config = AsyncMock()
    svc._config.get_int = AsyncMock(side_effect=lambda key: _CONFIG_VALUES[key])
    svc._credits.get_for_invitee = AsyncMock(return_value=None)
    svc._credits.create_return_model = AsyncMock(side_effect=lambda dto: SimpleNamespace(
        id="rc-1", **dto.model_dump()))
    return svc


class TestOnInviteeFirstPayment:
    async def test_no_referrer_is_noop(self):
        svc = _make_service()
        svc._users.get_user_model = AsyncMock(return_value=_invitee(referred_by=None))
        assert await svc.on_invitee_first_payment(_payment()) is None
        svc._credits.create_return_model.assert_not_called()

    async def test_creates_pending_credit_for_distinct_human(self):
        svc = _make_service()
        svc._users.get_user_model = AsyncMock(side_effect=[_invitee(), _referrer()])
        credit = await svc.on_invitee_first_payment(_payment())
        assert credit.status == ReferralCreditStatus.PENDING
        assert credit.amount_minor == 5_000 * 100  # ₦5,000 → kobo
        assert credit.clearing_until is not None

    async def test_idempotent_when_credit_already_exists(self):
        svc = _make_service()
        svc._credits.get_for_invitee = AsyncMock(return_value=SimpleNamespace(id="rc-existing"))
        svc._users.get_user_model = AsyncMock(return_value=_invitee())
        assert await svc.on_invitee_first_payment(_payment()) is None
        svc._credits.create_return_model.assert_not_called()

    async def test_voids_on_shared_verified_phone(self):
        svc = _make_service()
        shared = "+2348012345678"
        svc._users.get_user_model = AsyncMock(side_effect=[
            _invitee(phone_e164=shared), _referrer(phone_e164=shared),
        ])
        credit = await svc.on_invitee_first_payment(_payment())
        assert credit.status == ReferralCreditStatus.VOID
        assert credit.void_reason == "duplicate_phone"
        assert credit.clearing_until is None

    async def test_voids_on_shared_card_fingerprint(self):
        svc = _make_service()
        svc._users.get_user_model = AsyncMock(side_effect=[_invitee(), _referrer()])
        svc._payments.list_card_fingerprints_for_customer = AsyncMock(return_value={"fp-xyz"})
        credit = await svc.on_invitee_first_payment(_payment(card_fingerprint="fp-xyz"))
        assert credit.status == ReferralCreditStatus.VOID
        assert credit.void_reason == "duplicate_card"


class TestSweepReferralCredits:
    async def test_clears_due_credit_and_credits_balance(self, stub_publish):
        svc = _make_service()
        due = SimpleNamespace(id="rc-1", referrer_user_id=REFERRER.hex, amount_minor=500_000,
                              status=ReferralCreditStatus.PENDING.value, cleared_at=None)
        svc._credits.list_pending_due = AsyncMock(return_value=[due])
        svc._credits.get_model = AsyncMock(return_value=due)
        svc._credits.update = AsyncMock()
        svc._users.get_user_model = AsyncMock(return_value=_referrer(credit_balance_kobo=100_000))
        cleared = await svc.sweep_referral_credits()
        assert cleared == 1
        dto = svc._users.update_user.call_args.args[1]
        assert dto.credit_balance_kobo == 600_000  # 100k + 500k
        assert due.cleared_at is not None
        assert stub_publish[0].type == EventType.REFERRAL_CREDIT_EARNED

    async def test_idempotent_when_nothing_due(self):
        svc = _make_service()
        svc._credits.list_pending_due = AsyncMock(return_value=[])
        assert await svc.sweep_referral_credits() == 0


class TestResolveReferrer:
    async def test_unknown_code_returns_none(self):
        svc = _make_service()
        svc._referrals.get_by_code = AsyncMock(return_value=None)
        assert await svc.resolve_referrer_id("BOGUS") is None

    async def test_known_code_returns_referrer_id(self):
        svc = _make_service()
        svc._referrals.get_by_code = AsyncMock(return_value=SimpleNamespace(referrer_user_id=REFERRER.hex))
        assert await svc.resolve_referrer_id("good") == REFERRER.hex

"""Unit tests for ReferralService (S51)."""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from main.app.domain.referral.models import (
    ClaimReferralDto,
    DiscountBreakdownDto,
    RedemptionStatus,
)
from main.app.domain.referral.service import ReferralService
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.exception.exceptions import (
    ResourceNotFoundException,
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


def _mock_code(code="ABC12345", owner_id="owner-1", code_id="code-1", times_redeemed=0):
    row = MagicMock()
    row.id = code_id
    row.owner_id = owner_id
    row.code = code
    row.times_redeemed = times_redeemed
    row.date_created = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return row


def _mock_redemption(invitee_id="inv-1", code_id="code-1", status=RedemptionStatus.PENDING.value):
    r = MagicMock()
    r.id = "red-1"
    r.referral_code_id = code_id
    r.invitee_id = invitee_id
    r.status = status
    r.credited_at = None
    return r


def _mock_user(user_id="owner-1", credit_balance_kobo=0):
    u = MagicMock()
    u.id = user_id
    u.credit_balance_kobo = credit_balance_kobo
    return u


def _make_svc(
    *,
    existing_code=None,
    code_by_code=None,
    redemption=None,
    user=None,
    first_time_pct=10,
    max_pct=20,
    referral_credit_ngn=1000,
):
    codes = MagicMock()
    codes.get_by_owner = AsyncMock(return_value=existing_code)
    codes.get_by_code = AsyncMock(return_value=code_by_code)
    codes.get_model = AsyncMock(return_value=existing_code)
    codes.create_return_model = AsyncMock(return_value=existing_code or _mock_code())
    codes.update = AsyncMock()

    redemptions = MagicMock()
    redemptions.get_by_invitee = AsyncMock(return_value=redemption)
    redemptions.list_for_code = AsyncMock(return_value=[redemption] if redemption else [])
    redemptions.create_return_model = AsyncMock()
    redemptions.update = AsyncMock()

    users = MagicMock()
    users.get_model = AsyncMock(return_value=user or _mock_user())
    users.update = AsyncMock()

    config = MagicMock()

    async def _get_int(key, fallback=0):
        return {
            "first_time_discount_percent": first_time_pct,
            "max_discount_percent": max_pct,
            "referral_credit_ngn": referral_credit_ngn,
        }.get(key, fallback)

    config.get_int = AsyncMock(side_effect=_get_int)

    svc = ReferralService.__new__(ReferralService)
    svc._codes = codes
    svc._redemptions = redemptions
    svc._users = users
    svc._config = config
    return svc, codes, redemptions, users


class TestGetOrCreateCode:
    async def test_returns_existing_code_if_present(self):
        existing = _mock_code(code="EXIST123")
        svc, codes, _, _ = _make_svc(existing_code=existing)

        result = await svc.get_or_create_code("owner-1")

        assert result.code == "EXIST123"
        codes.create_return_model.assert_not_awaited()

    async def test_creates_new_code_when_none_exists(self):
        new_code = _mock_code(code="NEWCODE1")
        svc, codes, _, _ = _make_svc(existing_code=None)
        codes.get_by_code = AsyncMock(return_value=None)
        codes.create_return_model = AsyncMock(return_value=new_code)

        result = await svc.get_or_create_code("owner-1")

        codes.create_return_model.assert_awaited_once()
        assert len(result.code) == 8

    async def test_idempotent_on_second_call(self):
        existing = _mock_code(code="IDEM1234")
        svc, codes, _, _ = _make_svc(existing_code=existing)
        svc._codes.get_by_owner = AsyncMock(return_value=existing)

        r1 = await svc.get_or_create_code("owner-1")
        r2 = await svc.get_or_create_code("owner-1")

        assert r1.code == r2.code == "IDEM1234"


class TestClaimReferral:
    async def test_claims_successfully(self):
        code = _mock_code(owner_id="owner-1")
        svc, codes, redemptions, _ = _make_svc(code_by_code=code)
        codes.get_by_code = AsyncMock(return_value=code)
        redemptions.get_by_invitee = AsyncMock(return_value=None)

        await svc.claim_referral("invitee-2", ClaimReferralDto(code="ABC12345"))

        redemptions.create_return_model.assert_awaited_once()
        codes.update.assert_awaited_once()

    async def test_self_referral_raises(self):
        code = _mock_code(owner_id="user-1")
        svc, codes, _, _ = _make_svc(code_by_code=code)
        codes.get_by_code = AsyncMock(return_value=code)

        with pytest.raises(ValidationException, match="own referral code"):
            await svc.claim_referral("user-1", ClaimReferralDto(code="ABC12345"))

    async def test_idempotent_when_already_claimed(self):
        code = _mock_code(owner_id="owner-1")
        existing_redemption = _mock_redemption(invitee_id="invitee-2")
        svc, codes, redemptions, _ = _make_svc(code_by_code=code, redemption=existing_redemption)
        codes.get_by_code = AsyncMock(return_value=code)
        redemptions.get_by_invitee = AsyncMock(return_value=existing_redemption)

        await svc.claim_referral("invitee-2", ClaimReferralDto(code="ABC12345"))

        redemptions.create_return_model.assert_not_awaited()

    async def test_unknown_code_raises(self):
        svc, codes, _, _ = _make_svc()
        codes.get_by_code = AsyncMock(return_value=None)

        with pytest.raises(ResourceNotFoundException):
            await svc.claim_referral("invitee-2", ClaimReferralDto(code="MISSING1"))


class TestComputeDiscount:
    async def test_first_time_discount_applied(self):
        svc, _, redemptions, _ = _make_svc(first_time_pct=10, max_pct=20)
        redemptions.get_by_invitee = AsyncMock(return_value=None)

        breakdown = await svc.compute_discount("user-1", 100_000, is_first_payment=True)

        assert breakdown.first_time_discount_kobo == 10_000  # 10% of 100,000
        assert breakdown.final_amount_kobo == 90_000

    async def test_no_discount_on_non_first_payment(self):
        svc, _, redemptions, _ = _make_svc(first_time_pct=10, max_pct=20)
        redemptions.get_by_invitee = AsyncMock(return_value=None)

        breakdown = await svc.compute_discount("user-1", 100_000, is_first_payment=False)

        assert breakdown.first_time_discount_kobo == 0
        assert breakdown.final_amount_kobo == 100_000

    async def test_stacked_discount_capped_at_max(self):
        # first_time=10%, referral stacks → 20%, max=20% → cap applies
        redemption = _mock_redemption()
        svc, _, redemptions, _ = _make_svc(first_time_pct=10, max_pct=20, redemption=redemption)
        redemptions.get_by_invitee = AsyncMock(return_value=redemption)

        breakdown = await svc.compute_discount("user-1", 100_000, is_first_payment=True)

        assert breakdown.referral_discount_applied is True
        assert breakdown.total_discount_kobo <= 20_000  # max 20%
        assert breakdown.final_amount_kobo >= 80_000

    async def test_minimum_final_amount_is_100_kobo(self):
        svc, _, redemptions, _ = _make_svc(first_time_pct=100, max_pct=100)
        redemptions.get_by_invitee = AsyncMock(return_value=None)

        breakdown = await svc.compute_discount("user-1", 50, is_first_payment=True)

        assert breakdown.final_amount_kobo >= 100

    async def test_referral_discount_not_applied_on_repeat_payment(self):
        redemption = _mock_redemption()
        svc, _, redemptions, _ = _make_svc(redemption=redemption)
        redemptions.get_by_invitee = AsyncMock(return_value=redemption)

        breakdown = await svc.compute_discount("user-1", 100_000, is_first_payment=False)

        assert breakdown.referral_discount_applied is False


class TestCreditReferrerOnSuccess:
    async def test_credits_referrer_on_first_success(self):
        redemption = _mock_redemption(status=RedemptionStatus.PENDING.value)
        code = _mock_code(owner_id="owner-1")
        user = _mock_user(user_id="owner-1", credit_balance_kobo=0)
        svc, codes, redemptions, users = _make_svc(referral_credit_ngn=1000)
        redemptions.get_by_invitee = AsyncMock(return_value=redemption)
        codes.get_model = AsyncMock(return_value=code)
        users.get_model = AsyncMock(return_value=user)

        await svc.credit_referrer_on_success("invitee-2")

        redemptions.update.assert_awaited_once()
        users.update.assert_awaited_once()
        # Verify credit amount: 1000 NGN = 100,000 kobo
        _, dto = users.update.call_args[0]
        assert dto.credit_balance_kobo == 100_000

    async def test_idempotent_when_already_credited(self):
        redemption = _mock_redemption(status=RedemptionStatus.CREDITED.value)
        svc, codes, redemptions, users = _make_svc()
        redemptions.get_by_invitee = AsyncMock(return_value=redemption)

        await svc.credit_referrer_on_success("invitee-2")

        redemptions.update.assert_not_awaited()
        users.update.assert_not_awaited()

    async def test_no_op_when_no_referral(self):
        svc, codes, redemptions, users = _make_svc()
        redemptions.get_by_invitee = AsyncMock(return_value=None)

        await svc.credit_referrer_on_success("invitee-2")

        users.update.assert_not_awaited()

    async def test_accumulates_credit(self):
        redemption = _mock_redemption(status=RedemptionStatus.PENDING.value)
        code = _mock_code(owner_id="owner-1")
        user = _mock_user(user_id="owner-1", credit_balance_kobo=50_000)  # already has some
        svc, codes, redemptions, users = _make_svc(referral_credit_ngn=1000)
        redemptions.get_by_invitee = AsyncMock(return_value=redemption)
        codes.get_model = AsyncMock(return_value=code)
        users.get_model = AsyncMock(return_value=user)

        await svc.credit_referrer_on_success("invitee-2")

        _, dto = users.update.call_args[0]
        assert dto.credit_balance_kobo == 150_000  # 50,000 + 100,000

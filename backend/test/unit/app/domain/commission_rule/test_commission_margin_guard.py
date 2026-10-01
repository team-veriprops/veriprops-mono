"""CommissionMarginGuard — every tier keeps a minimum platform margin (§20.1 / D97).

A tier's roles are each paid a fixed commission, and a tier's price is set on a different screen,
so nothing but this rule stops the two from crossing: a price cut, a commission raise or a margin
raise must each be refused when it would leave any tier below the configured minimum margin.
Repos mocked, no DB.
"""
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.core.state.status import AgentRole, VerificationTier
from main.app.domain.commission_rule.margin import CommissionMarginGuard, find_margin_breach
from main.app.domain.commission_rule.models import DEFAULT_ROLE_COMMISSION_NGN_KOBO
from main.app.domain.system_config.models import CONFIG_DEFAULTS, ConfigKey
from main.app.domain.verification.pricing import TIER_PRICE_NGN_KOBO
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


def _guard(commissions=None, prices=None, margin=None, bonus=None):
    """A guard over stored rows. Commissions default to the seeded per-role amounts (what
    migration 0002 leaves); prices and the margin default to no row, i.e. their fallbacks."""
    commissions = DEFAULT_ROLE_COMMISSION_NGN_KOBO if commissions is None else commissions
    guard = object.__new__(CommissionMarginGuard)
    guard._commission_rule_repo = AsyncMock()
    guard._pricing_tier_config_repo = AsyncMock()
    guard._system_config_repo = AsyncMock()
    guard._commission_rule_repo.list_all = AsyncMock(return_value=[
        SimpleNamespace(role=role.value, amount_ngn_kobo=amount)
        for role, amount in commissions.items()
    ])
    guard._pricing_tier_config_repo.list_all = AsyncMock(return_value=[
        SimpleNamespace(tier=tier.value, price_ngn_kobo=price) for tier, price in (prices or {}).items()
    ])
    stored_config = {
        ConfigKey.COMMISSION_MIN_MARGIN_PCT.value: margin,
        ConfigKey.REMOTE_JOB_BONUS_NGN_KOBO.value: bonus,
    }
    guard._system_config_repo.get_by_key = AsyncMock(side_effect=lambda key: (
        SimpleNamespace(value_json=stored_config[key]) if stored_config.get(key) is not None else None
    ))
    return guard


class TestFindMarginBreach:
    def test_the_seeded_defaults_leave_every_tier_its_margin(self):
        breach = find_margin_breach(
            TIER_PRICE_NGN_KOBO, DEFAULT_ROLE_COMMISSION_NGN_KOBO,
            CONFIG_DEFAULTS[ConfigKey.COMMISSION_MIN_MARGIN_PCT],
        )
        assert breach is None

    def test_a_tier_whose_commissions_eat_the_margin_is_named(self):
        # BASIC pays only REGISTRY: ₦40,000 of ₦50,000 leaves 20%, below a 30% minimum.
        commissions = {**DEFAULT_ROLE_COMMISSION_NGN_KOBO, AgentRole.REGISTRY: 4_000_000}
        breach = find_margin_breach(TIER_PRICE_NGN_KOBO, commissions, 30)
        assert breach is not None
        assert breach.tier == VerificationTier.BASIC
        assert (breach.price_minor, breach.commissions_minor) == (5_000_000, 4_000_000)

    def test_margin_exactly_at_the_minimum_passes(self):
        commissions = {**DEFAULT_ROLE_COMMISSION_NGN_KOBO, AgentRole.REGISTRY: 3_500_000}  # 30% left
        assert find_margin_breach({VerificationTier.BASIC: 5_000_000}, commissions, 30) is None


class TestRemoteBonus:
    """The remote bonus is paid on top of a fixed commission, so the margin counts it — as the
    worst case, every role on the tier carrying it (§20.1 / D97)."""

    def test_the_bonus_is_counted_once_per_role_on_the_tier(self):
        # STANDARD pays three roles: ₦48,800 of commissions + 3 × ₦12,000 = ₦84,800 of ₦120,000,
        # 29% left — just below 30%. BASIC (one role) keeps ₦18,000 of ₦50,000 = 36%.
        breach = find_margin_breach(TIER_PRICE_NGN_KOBO, DEFAULT_ROLE_COMMISSION_NGN_KOBO, 30, 1_200_000)
        assert breach is not None and breach.tier == VerificationTier.STANDARD
        assert breach.commissions_minor == 4_880_000 + 3 * 1_200_000

    def test_the_refusal_says_bonuses_were_counted(self):
        breach = find_margin_breach(TIER_PRICE_NGN_KOBO, DEFAULT_ROLE_COMMISSION_NGN_KOBO, 30, 1_200_000)
        assert "remote bonuses" in breach.message()

    async def test_refuses_a_bonus_that_breaks_a_tier(self):
        with pytest.raises(ValidationException, match="Standard"):
            await _guard().check(remote_bonus_minor=1_200_000)

    async def test_reads_the_stored_bonus(self):
        with pytest.raises(ValidationException, match="Standard"):
            await _guard(bonus=1_200_000).check()

    async def test_a_small_bonus_passes(self):
        await _guard().check(remote_bonus_minor=500_000)


class TestGuardCheck:
    async def test_passes_on_the_seeded_configuration(self):
        await _guard().check()

    async def test_refuses_a_commission_raise_that_breaks_a_tier(self):
        with pytest.raises(ValidationException, match="Basic"):
            await _guard().check(commission_overrides={AgentRole.REGISTRY: 4_000_000})

    async def test_refuses_a_price_cut_that_breaks_a_tier(self):
        with pytest.raises(ValidationException, match="Standard"):
            await _guard().check(price_overrides={VerificationTier.STANDARD: 6_000_000})

    async def test_refuses_a_margin_raise_that_breaks_a_tier(self):
        # The defaults leave BASIC 60%, STANDARD ~59% and PREMIUM ~72%. Demanding 65% breaks
        # BASIC first (tiers are checked in order); with BASIC repriced, STANDARD is next.
        with pytest.raises(ValidationException, match="Basic"):
            await _guard().check(min_margin_pct=65)
        with pytest.raises(ValidationException, match="Standard"):
            await _guard(prices={VerificationTier.BASIC: 10_000_000}).check(min_margin_pct=65)

    async def test_reads_the_stored_configuration(self):
        guard = _guard(
            commissions={AgentRole.REGISTRY: 1_000_000},
            prices={VerificationTier.BASIC: 1_200_000},
            margin=30,
        )
        with pytest.raises(ValidationException, match="Basic"):
            await guard.check()

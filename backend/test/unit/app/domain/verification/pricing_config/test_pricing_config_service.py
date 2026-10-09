"""PricingConfigService (§18.1, D36) — DB-backed tier prices with static fallback,
line-item replace, and the upgrade-delta view. Repos mocked, no DB."""
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from test.utils.repo_fakes import fake_upsert, first_matching

from main.app.core.state.status import VerificationTier
from main.app.domain.verification.pricing import TIER_PRICE_NGN_KOBO
from main.app.domain.verification.pricing_config.models import LineItemInputDto
from main.app.domain.verification.pricing_config.service import PricingConfigService
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
    session.execute = AsyncMock()  # advisory locks (`advisory_xact_lock`) run a statement
    token = db_session_ctx.set(session)
    yield session
    db_session_ctx.reset(token)


def _make_service():
    svc = object.__new__(PricingConfigService)
    svc._tiers = AsyncMock()
    svc._line_items = AsyncMock()
    svc._audit = MagicMock()
    svc._audit.schedule = MagicMock()
    svc._margin_guard = AsyncMock()
    return svc


class TestTierPriceResolution:
    async def test_reads_db_price_when_present(self):
        svc = _make_service()
        svc._tiers.get_for_tier = AsyncMock(return_value=SimpleNamespace(price_ngn_kobo=9_999_999))
        assert await svc.tier_price_kobo(VerificationTier.STANDARD) == 9_999_999

    async def test_falls_back_to_static_default(self):
        svc = _make_service()
        svc._tiers.get_for_tier = AsyncMock(return_value=None)
        assert await svc.tier_price_kobo(VerificationTier.BASIC) == TIER_PRICE_NGN_KOBO[VerificationTier.BASIC]


def _items(*amounts):
    return [LineItemInputDto(label=f"Item {n}", amount_minor=amount) for n, amount in enumerate(amounts)]


def _writable(svc):
    """Repos that record the tier row and the replaced line items."""
    rows = [SimpleNamespace(id="pt-1", tier=VerificationTier.BASIC.value, price_ngn_kobo=5_000_000, deleted=False)]
    svc._tiers.upsert = fake_upsert(
        lambda values: first_matching(rows, tier=values["tier"]),
        lambda values: rows.append(SimpleNamespace(id="pt-new", deleted=False, **values)) or rows[-1],
    )
    svc._line_items.list_for_tier = AsyncMock(return_value=[SimpleNamespace(id="li-old")])
    svc._line_items.soft_delete = AsyncMock()
    svc._line_items.create_return_model = AsyncMock(
        side_effect=lambda dto: SimpleNamespace(id="li-new", **dto.model_dump()))
    return rows


class TestSetTierPricing:
    """A tier's price and its itemised breakdown are one edit (§18.1): saved apart, a price
    change left the customer-facing breakdown adding up to the old price."""

    async def test_writes_the_price_and_replaces_the_items_together(self):
        svc = _make_service()
        rows = _writable(svc)
        await svc.set_tier_pricing(VerificationTier.BASIC, 7_000_000, _items(3_000_000, 4_000_000), "admin-1")
        assert rows[0].price_ngn_kobo == 7_000_000
        # One statement on the live tier key, so a concurrent first save can't insert twice.
        assert svc._tiers.upsert.await_args.kwargs == {"unique_index": "uq_pricing_tier_config_tier"}
        svc._line_items.soft_delete.assert_awaited_once_with("li-old")
        written = [c.args[0] for c in svc._line_items.create_return_model.await_args_list]
        assert [(w.amount_minor, w.sort_order) for w in written] == [(3_000_000, 0), (4_000_000, 1)]
        svc._audit.schedule.assert_called_once()

    async def test_no_items_leaves_the_tier_without_a_breakdown(self):
        svc = _make_service()
        _writable(svc)
        await svc.set_tier_pricing(VerificationTier.BASIC, 7_000_000, [], "admin-1")
        svc._line_items.soft_delete.assert_awaited_once_with("li-old")
        svc._line_items.create_return_model.assert_not_awaited()

    async def test_items_that_do_not_add_up_to_the_price_are_refused(self):
        svc = _make_service()
        _writable(svc)
        with pytest.raises(ValidationException, match="add up"):
            await svc.set_tier_pricing(VerificationTier.BASIC, 7_000_000, _items(3_000_000, 3_999_999), "admin-1")
        svc._tiers.upsert.assert_not_awaited()
        svc._line_items.soft_delete.assert_not_awaited()

    @pytest.mark.parametrize("price, items", [(-1, []), (7_000_000, _items(7_000_001, -1))])
    async def test_negative_amounts_are_refused(self, price, items):
        svc = _make_service()
        _writable(svc)
        with pytest.raises(ValidationException):
            await svc.set_tier_pricing(VerificationTier.BASIC, price, items, "admin-1")
        svc._tiers.upsert.assert_not_awaited()

    async def test_a_blank_label_is_refused(self):
        svc = _make_service()
        _writable(svc)
        items = [LineItemInputDto(label="  ", amount_minor=7_000_000)]
        with pytest.raises(ValidationException):
            await svc.set_tier_pricing(VerificationTier.BASIC, 7_000_000, items, "admin-1")

    async def test_the_proposed_price_is_checked_against_the_commission_margin(self):
        svc = _make_service()
        _writable(svc)
        await svc.set_tier_pricing(VerificationTier.BASIC, 7_000_000, [], "admin-1")
        svc._margin_guard.check.assert_awaited_once_with(price_overrides={VerificationTier.BASIC: 7_000_000})

    async def test_a_price_that_breaks_the_margin_writes_nothing(self):
        svc = _make_service()
        _writable(svc)
        svc._margin_guard.check = AsyncMock(side_effect=ValidationException(message="below the margin"))
        with pytest.raises(ValidationException):
            await svc.set_tier_pricing(VerificationTier.BASIC, 1, _items(1), "admin-1")
        svc._tiers.upsert.assert_not_awaited()
        svc._line_items.soft_delete.assert_not_awaited()


class TestView:
    async def test_view_includes_prices_and_upgrade_deltas(self):
        svc = _make_service()
        svc._tiers.get_for_tier = AsyncMock(return_value=None)  # all static defaults
        svc._line_items.list_for_tier = AsyncMock(return_value=[])
        view = await svc.view()
        assert len(view.tiers) == len(VerificationTier)
        # BASIC→STANDARD, BASIC→PREMIUM, STANDARD→PREMIUM = 3 upgrade paths.
        assert len(view.upgrade_deltas) == 3
        std_to_prem = next(d for d in view.upgrade_deltas
                           if d.from_tier == VerificationTier.STANDARD and d.to_tier == VerificationTier.PREMIUM)
        assert std_to_prem.delta_minor == (
            TIER_PRICE_NGN_KOBO[VerificationTier.PREMIUM] - TIER_PRICE_NGN_KOBO[VerificationTier.STANDARD]
        )

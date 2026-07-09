"""PricingConfigService (§18.1, D36) — DB-backed tier prices with static fallback,
line-item replace, and the upgrade-delta view. Repos mocked, no DB."""
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.core.state.status import VerificationTier
from main.app.domain.verification.pricing import TIER_PRICE_NGN_KOBO
from main.app.domain.verification.pricing_config.models import LineItemInputDto
from main.app.domain.verification.pricing_config.service import PricingConfigService
from main.appodus_utils.db.session import db_session_ctx


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


def _make_service():
    svc = object.__new__(PricingConfigService)
    svc._tiers = AsyncMock()
    svc._line_items = AsyncMock()
    svc._audit = MagicMock()
    svc._audit.schedule = MagicMock()
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


class TestSetTierPrice:
    async def test_updates_existing_row(self):
        svc = _make_service()
        svc._tiers.get_for_tier = AsyncMock(return_value=SimpleNamespace(id="pt-1"))
        svc._tiers.update = AsyncMock()
        svc._tiers.get_model = AsyncMock(return_value=SimpleNamespace(id="pt-1", price_ngn_kobo=7_000_000))
        row = await svc.set_tier_price(VerificationTier.BASIC, 7_000_000, "admin-1")
        assert row.price_ngn_kobo == 7_000_000
        svc._tiers.update.assert_awaited_once()
        svc._audit.schedule.assert_called_once()


class TestSetLineItems:
    async def test_replaces_line_items(self):
        svc = _make_service()
        svc._line_items.list_for_tier = AsyncMock(return_value=[SimpleNamespace(id="li-old")])
        svc._line_items.soft_delete = AsyncMock()
        svc._line_items.create_return_model = AsyncMock(side_effect=lambda dto: SimpleNamespace(id="li-new", **dto.model_dump()))
        items = [LineItemInputDto(label="Registry search", amount_minor=2_000_000),
                 LineItemInputDto(label="Field visit", amount_minor=3_000_000)]
        written = await svc.set_line_items(VerificationTier.STANDARD, items, "admin-1")
        svc._line_items.soft_delete.assert_awaited_once_with("li-old")
        assert len(written) == 2
        assert written[0].sort_order == 0 and written[1].sort_order == 1


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

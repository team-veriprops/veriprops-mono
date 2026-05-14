"""Unit tests for PricingService DB-backed methods (S54)."""
from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.domain.verification.pricing.models import (
    PricingLineItemDto,
    PricingTierConfigDto,
    PricingUpgradeDeltaDto,
    UpsertPricingLineItemPayload,
    UpsertPricingTierDto,
    UpsertUpgradeDeltaDto,
)
from main.app.domain.verification.pricing.service import PricingService
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


def _make_tier_config(tier="BASIC", currency="NGN"):
    cfg = MagicMock()
    cfg.id = "cfg-001"
    cfg.tier = tier
    cfg.label = f"{tier} verification"
    cfg.currency = currency
    cfg.service_fee_minor = 1500000
    cfg.is_active = True
    cfg.updated_by = None
    cfg.date_updated = None
    return cfg


def _make_line_item(label="Registry search", amount=13000000, sort_order=0):
    li = MagicMock()
    li.id = "li-001"
    li.label = label
    li.amount_minor = amount
    li.description = "desc"
    li.sort_order = sort_order
    return li


def _make_delta(from_tier="BASIC", to_tier="STANDARD", delta=15000000):
    row = MagicMock()
    row.id = "delta-001"
    row.from_tier = from_tier
    row.to_tier = to_tier
    row.delta_minor = delta
    row.currency = "NGN"
    row.updated_by = None
    row.date_updated = None
    return row


def _make_svc():
    svc = PricingService.__new__(PricingService)
    tier_repo = MagicMock()
    line_item_repo = MagicMock()
    delta_repo = MagicMock()
    svc._tier_repo = tier_repo
    svc._line_item_repo = line_item_repo
    svc._delta_repo = delta_repo
    return svc, tier_repo, line_item_repo, delta_repo


class TestListTierConfigs:
    async def test_returns_all_active_tiers_with_line_items(self):
        svc, tier_repo, li_repo, _ = _make_svc()
        cfg = _make_tier_config("BASIC")
        li = _make_line_item()
        tier_repo.list_all_active = AsyncMock(return_value=[cfg])
        li_repo.list_for_config = AsyncMock(return_value=[li])

        result = await svc.list_tier_configs()

        assert len(result) == 1
        assert result[0].tier == "BASIC"
        assert len(result[0].line_items) == 1
        assert result[0].line_items[0].label == "Registry search"

    async def test_empty_when_no_active_tiers(self):
        svc, tier_repo, li_repo, _ = _make_svc()
        tier_repo.list_all_active = AsyncMock(return_value=[])

        result = await svc.list_tier_configs()

        assert result == []


class TestUpsertTier:
    async def test_creates_new_tier_when_not_exists(self):
        svc, tier_repo, li_repo, _ = _make_svc()
        tier_repo.get_for_tier_currency = AsyncMock(return_value=None)
        new_cfg = _make_tier_config("BASIC")
        tier_repo.create = AsyncMock(return_value=new_cfg)
        li_repo.delete_for_config = AsyncMock()
        li_repo.create = AsyncMock()
        li_repo.list_for_config = AsyncMock(return_value=[])

        dto = UpsertPricingTierDto(
            tier="BASIC",
            label="Basic verification",
            currency="NGN",
            service_fee_minor=1500000,
            line_items=[UpsertPricingLineItemPayload(label="Registry search", amount_minor=13000000, sort_order=0)],
        )
        result = await svc.upsert_tier(dto, "admin-1")

        tier_repo.create.assert_awaited_once()
        li_repo.delete_for_config.assert_awaited_once()
        li_repo.create.assert_awaited_once()
        assert result.tier == "BASIC"

    async def test_updates_existing_tier_and_replaces_line_items(self):
        svc, tier_repo, li_repo, _ = _make_svc()
        existing_cfg = _make_tier_config("BASIC")
        tier_repo.get_for_tier_currency = AsyncMock(return_value=existing_cfg)
        updated_cfg = _make_tier_config("BASIC")
        tier_repo.update = AsyncMock()
        tier_repo.get_model = AsyncMock(return_value=updated_cfg)
        li_repo.delete_for_config = AsyncMock()
        li_repo.create = AsyncMock()
        li_repo.list_for_config = AsyncMock(return_value=[])

        dto = UpsertPricingTierDto(
            tier="BASIC",
            label="Basic updated",
            currency="NGN",
            service_fee_minor=2000000,
            line_items=[],
        )
        result = await svc.upsert_tier(dto, "admin-1")

        tier_repo.update.assert_awaited_once()
        li_repo.delete_for_config.assert_awaited_once()
        assert result.tier == "BASIC"

    async def test_records_updated_by(self):
        svc, tier_repo, li_repo, _ = _make_svc()
        tier_repo.get_for_tier_currency = AsyncMock(return_value=None)
        new_cfg = _make_tier_config("STANDARD")
        tier_repo.create = AsyncMock(return_value=new_cfg)
        li_repo.delete_for_config = AsyncMock()
        li_repo.create = AsyncMock()
        li_repo.list_for_config = AsyncMock(return_value=[])

        dto = UpsertPricingTierDto(
            tier="STANDARD",
            label="Standard",
            currency="NGN",
            service_fee_minor=2500000,
            line_items=[],
        )
        await svc.upsert_tier(dto, "admin-007")

        call_args = tier_repo.create.call_args[0][0]
        assert call_args.updated_by == "admin-007"


class TestUpsertUpgradeDelta:
    async def test_creates_new_delta_when_not_exists(self):
        svc, tier_repo, li_repo, delta_repo = _make_svc()
        delta_repo.get_for_pair = AsyncMock(return_value=None)
        new_row = _make_delta()
        delta_repo.create = AsyncMock(return_value=new_row)

        dto = UpsertUpgradeDeltaDto(from_tier="BASIC", to_tier="STANDARD", delta_minor=15000000, currency="NGN")
        result = await svc.upsert_upgrade_delta(dto, "admin-1")

        delta_repo.create.assert_awaited_once()
        assert result.from_tier == "BASIC"
        assert result.to_tier == "STANDARD"

    async def test_updates_existing_delta(self):
        svc, tier_repo, li_repo, delta_repo = _make_svc()
        existing_row = _make_delta()
        delta_repo.get_for_pair = AsyncMock(return_value=existing_row)
        delta_repo.update = AsyncMock()
        updated_row = _make_delta(delta=20000000)
        delta_repo.get_model = AsyncMock(return_value=updated_row)

        dto = UpsertUpgradeDeltaDto(from_tier="BASIC", to_tier="STANDARD", delta_minor=20000000, currency="NGN")
        result = await svc.upsert_upgrade_delta(dto, "admin-1")

        delta_repo.update.assert_awaited_once()
        assert result.delta_minor == 20000000


class TestListUpgradeDeltas:
    async def test_returns_all_deltas(self):
        svc, _, _, delta_repo = _make_svc()
        delta_repo.list_all = AsyncMock(return_value=[_make_delta(), _make_delta("STANDARD", "PREMIUM", 25000000)])

        result = await svc.list_upgrade_deltas()

        assert len(result) == 2

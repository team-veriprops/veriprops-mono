"""Seed/registry parity guard.

All reference data is seeded by migration `0001_initial_schema` through pure
row-builder functions that translate the app-side registries into raw column
values (there is no app-startup seeder). These tests pin that translation —
enum members reduced to `.value`, JSON encoding, the commission-rate math —
so registry drift or a mistranslated builder fails CI without needing a DB.
Raw DB strings are asserted deliberately (wire/DB-string compatibility).
"""
import importlib.util
import json
from pathlib import Path

from main.app.config.settings import settings
from main.app.core.state.dependencies import roles_for_tier
from main.app.core.state.status import VerificationTier
from main.app.domain.commission_rule.models import BPS_PER_PERCENT
from main.app.domain.system_config.models import CONFIG_DEFAULTS, CONFIG_DESCRIPTIONS
from main.app.domain.user.auth.consent.content import LEGAL_DOCUMENT_CONTENT
from main.app.domain.verification.pricing import TIER_PRICE_NGN_KOBO
from main.app.domain.verification.scoring.models import DEFAULT_TRUST_WEIGHTS

# backend/test/unit/app/<this file> -> backend/ is parents[3].
_BACKEND_ROOT = Path(__file__).resolve().parents[3]


def _load_initial_migration():
    migration_path = _BACKEND_ROOT / "main" / "alembic" / "versions" / "0001_initial_schema.py"
    spec = importlib.util.spec_from_file_location("veriprops_initial_migration", migration_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_migration = _load_initial_migration()


def test_consent_rows_match_content_registry():
    rows = {(r["type"], r["consent_version"]): r for r in _migration._consent_document_rows()}
    assert set(rows) == {
        (c.type.value, c.consent_version) for c in LEGAL_DOCUMENT_CONTENT.values()
    }
    for content in LEGAL_DOCUMENT_CONTENT.values():
        row = rows[(content.type.value, content.consent_version)]
        assert row["title"] == content.title
        assert row["href"] == content.href
        assert row["body"] == content.body
        assert row["signoff_status"] == content.signoff_status.value
        assert row["effective_at"] == content.effective_at


def test_trust_weight_rows_match_defaults_and_sum_to_100():
    rows = {(r["tier"], r["role"]): r["weight_percent"] for r in _migration._trust_weight_rows()}
    expected = {
        (tier.value, role.value): weight
        for tier, role_weights in DEFAULT_TRUST_WEIGHTS.items()
        for role, weight in role_weights.items()
    }
    assert rows == expected
    for tier in DEFAULT_TRUST_WEIGHTS:
        assert sum(w for (t, _r), w in rows.items() if t == tier.value) == 100


def test_system_config_rows_cover_every_key():
    rows = {r["key"]: r for r in _migration._system_config_rows()}
    assert set(rows) == {key.value for key in CONFIG_DEFAULTS}
    for key, default in CONFIG_DEFAULTS.items():
        assert json.loads(rows[key.value]["value_json"]) == default
        assert rows[key.value]["description"] == CONFIG_DESCRIPTIONS.get(key)


def test_commission_rates_reproduce_flat_model():
    rows = {(r["role"], r["tier"]): r["rate_bps"] for r in _migration._commission_rule_rows()}
    # Every tier's full role set (TIER_ROLES) gets a rate — D30 equivalence with
    # the old roles_for_tier seeding loop.
    assert set(rows) == {
        (role.value, tier.value) for tier in VerificationTier for role in roles_for_tier(tier)
    }
    for tier, role_weights in DEFAULT_TRUST_WEIGHTS.items():
        for role, weight in role_weights.items():
            expected = round(weight * BPS_PER_PERCENT * settings.AGENT_COMMISSION_SHARE)
            assert rows[(role.value, tier.value)] == expected


def test_pricing_rows_match_tier_prices():
    tier_rows = {r["tier"]: r["price_ngn_kobo"] for r in _migration._pricing_tier_rows()}
    assert tier_rows == {tier.value: price for tier, price in TIER_PRICE_NGN_KOBO.items()}

    line_items = {r["tier"]: r for r in _migration._pricing_line_item_rows()}
    assert set(line_items) == set(tier_rows)
    for tier, price in TIER_PRICE_NGN_KOBO.items():
        item = line_items[tier.value]
        assert item["label"] == "Verification service fee"
        assert item["amount_minor"] == price
        assert item["sort_order"] == 0

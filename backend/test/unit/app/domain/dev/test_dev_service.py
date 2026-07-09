"""Dev/QA automation-determinism contract (CLAUDE.md). Guards the production gate and the
reset table list — the seed/reset harness underpins all live drive-throughs, so a regression
here silently breaks autonomous QA."""
import pytest

from main.app import core as _core, domain as _domain  # register models onto metadata
from main.app.config.settings import settings
from main.app.domain.dev import controller as dev_controller
from main.app.domain.dev.service import _RESET_TABLES
from main.appodus_utils import BaseEntity
from main.appodus_utils.config.settings import Environment
from main.appodus_utils.exception.exceptions import ResourceNotFoundException

# Reference/identity tables reset() must never clear (seeded once at startup).
_PRESERVED_TABLES = {
    "consent_documents", "user_consents", "trust_score_weight_config", "key_values",
    "users", "pricing_tier_config", "pricing_line_items", "commission_rules", "system_config",
}


class TestProductionGate:
    def test_require_non_prod_raises_in_production(self, monkeypatch):
        monkeypatch.setattr(settings, "ENVIRONMENT", Environment.PRODUCTION)
        with pytest.raises(ResourceNotFoundException):
            dev_controller._require_non_prod()

    @pytest.mark.parametrize("env", [Environment.LOCAL, Environment.TEST, Environment.DEVELOPMENT, Environment.STAGING])
    def test_require_non_prod_passes_outside_production(self, monkeypatch, env):
        monkeypatch.setattr(settings, "ENVIRONMENT", env)
        dev_controller._require_non_prod()  # must not raise


class TestResetTableList:
    def test_reset_targets_are_real_tables(self):
        """A typo'd table name would 500 the QA reset at runtime — assert each exists."""
        _ = (_core, _domain)
        known = set(BaseEntity.metadata.tables.keys())
        unknown = [t for t in _RESET_TABLES if t not in known]
        assert not unknown, f"_RESET_TABLES references non-existent tables: {unknown}"

    def test_reset_never_clears_reference_or_super_admin_tables(self):
        leaked = _PRESERVED_TABLES.intersection(_RESET_TABLES)
        assert not leaked, f"reset() would wipe preserved reference data: {sorted(leaked)}"

    def test_reset_table_list_has_no_duplicates(self):
        assert len(_RESET_TABLES) == len(set(_RESET_TABLES))

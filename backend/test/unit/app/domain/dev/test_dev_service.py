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

    @pytest.mark.parametrize("env", [Environment.DEV_PERSONAL, Environment.TEST, Environment.DEVELOPMENT, Environment.STAGING])
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


class TestMessageDeterminismHelpers:
    """/dev/messages/* back the drive-through's messaging_retry stage: latest_message is a
    read-only bookkeeping snapshot; rewind_message must only touch retry timestamps —
    status/retry_count stay owned by the pipeline under test."""

    @staticmethod
    async def _call(method: str, row, *args, **kwargs):
        """Run a DevSeedService method against a mocked context session; returns
        (result, executed SQL string)."""
        import uuid  # noqa: F401 — used by callers building rows
        from contextlib import asynccontextmanager
        from unittest.mock import AsyncMock, MagicMock

        from main.app.domain.dev.service import DevSeedService
        from main.appodus_utils.db.session import db_session_ctx

        session = MagicMock()
        session.in_transaction.return_value = False

        @asynccontextmanager
        async def _begin():
            yield

        session.begin = _begin
        session.flush = AsyncMock()
        result = MagicMock()
        result.first.return_value = row
        session.execute = AsyncMock(return_value=result)

        svc = object.__new__(DevSeedService)
        token = db_session_ctx.set(session)
        try:
            out = await getattr(svc, method)(*args, **kwargs)
        finally:
            db_session_ctx.reset(token)
        return out, str(session.execute.call_args.args[0])

    async def test_latest_message_not_found_shape(self):
        out, _ = await self._call("latest_message", None, "nobody@veriprops.io")
        assert out == {"found": False}

    async def test_latest_message_snapshot_targets_newest_matching_row(self):
        import uuid
        from types import SimpleNamespace
        row = SimpleNamespace(id=uuid.uuid4(), status="retrying", retry_count=1,
                              next_retry_at_set=True, expires_at_set=False, error="boom")
        out, sql = await self._call("latest_message", row, "qa-customer@veriprops.io")
        assert out["found"] and out["status"] == "retrying" and out["retry_count"] == 1
        assert out["id"] == row.id.hex
        assert "ORDER BY date_created DESC LIMIT 1" in sql and '"to"::text ILIKE' in sql

    async def test_rewind_touches_only_the_retry_timestamp(self):
        import uuid
        from types import SimpleNamespace
        row = SimpleNamespace(id=uuid.uuid4())
        out, sql = await self._call("rewind_message", row, "qa-customer@veriprops.io")
        set_clause = sql.split("WHERE")[0]
        assert "next_retry_at = now() - interval '1 second'" in set_clause
        assert "expires_at" not in set_clause  # not rewound unless asked
        assert "status" not in set_clause and "retry_count" not in set_clause
        assert out == {"rewound": True, "id": row.id.hex}

    async def test_rewind_expiry_includes_expires_at(self):
        import uuid
        from types import SimpleNamespace
        row = SimpleNamespace(id=uuid.uuid4())
        _, sql = await self._call("rewind_message", row, "x@veriprops.io", rewind_expiry=True)
        assert "expires_at = now() - interval '1 second'" in sql.split("WHERE")[0]

    async def test_rewind_missing_row_reports_not_rewound(self):
        out, _ = await self._call("rewind_message", None, "nobody@veriprops.io")
        assert out == {"rewound": False, "id": None}

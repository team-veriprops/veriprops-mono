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
# `user_consents` is deliberately NOT here — those are per-user acceptances, cleared with
# the users themselves and re-recorded by seed() (the documents they reference are kept).
_PRESERVED_TABLES = {
    "consent_documents", "trust_score_weight_config", "key_values",
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


SUPER_ADMIN_ID = "00000000-0000-0000-0000-0000000000ad"


class TestSeededConsents:
    """Seeded users are inserted directly, bypassing the signup service that records
    consents. Without consent rows every seeded persona is trapped behind the
    non-dismissible re-acceptance modal (§3.2) on every authenticated page, which blocks
    browser automation outright — so seed() must record them itself."""

    @staticmethod
    async def _seed_adds():
        """Run seed() against a mocked session; returns everything it added."""
        from contextlib import asynccontextmanager
        from types import SimpleNamespace
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

        # seed() issues two reads: the consent-document lookup (two required docs, each
        # with an older superseded row, so the seed must pick the current version) and the
        # super-admin id lookup.
        docs = MagicMock()
        docs.all.return_value = [
            SimpleNamespace(type="PLATFORM_TERMS", consent_version="2.0.0"),
            SimpleNamespace(type="PRIVACY_POLICY", consent_version="2.0.0"),
            SimpleNamespace(type="PLATFORM_TERMS", consent_version="1.0.0"),
            SimpleNamespace(type="PRIVACY_POLICY", consent_version="1.0.0"),
        ]
        admin = MagicMock()
        admin.first.return_value = SimpleNamespace(id=SUPER_ADMIN_ID)

        async def _execute(statement, *_args, **_kwargs):
            return admin if "FROM users" in str(statement) else docs

        session.execute = AsyncMock(side_effect=_execute)

        added = []
        session.add = added.append

        svc = object.__new__(DevSeedService)
        token = db_session_ctx.set(session)
        try:
            await svc.seed()
        finally:
            db_session_ctx.reset(token)
        return added

    async def test_every_seeded_user_accepts_all_required_consents(self):
        from main.app.domain.user.auth.consent.models import (
            REQUIRED_SIGNUP_CONSENTS,
            UserConsent,
        )
        from main.app.domain.user.models import User

        added = await self._seed_adds()
        user_ids = {str(u.id) for u in added if isinstance(u, User)}
        consents = [c for c in added if isinstance(c, UserConsent)]
        assert user_ids, "seed() created no users"

        required = {t.value for t in REQUIRED_SIGNUP_CONSENTS}
        by_user: dict[str, set[str]] = {}
        for consent in consents:
            by_user.setdefault(consent.user_id, set()).add(consent.document_type)

        # Any seeded user missing one is a user the modal would trap.
        missing = {uid: required - by_user.get(uid, set()) for uid in user_ids}
        assert not any(missing.values()), f"seeded users missing consents: {missing}"

    async def test_seeded_consents_use_the_current_document_version(self):
        from main.app.domain.user.auth.consent.models import UserConsent

        added = await self._seed_adds()
        versions = {c.consent_version for c in added if isinstance(c, UserConsent)}
        # Accepting a superseded version still counts as "missing" to the modal check.
        assert versions == {"2.0.0"}, f"expected only the current version, got {versions}"

    async def test_surviving_super_admin_also_gets_consents(self):
        """The super-admin is created by migration 0001 and survives reset(), so it is not
        among the seeded users — but an admin trapped by the modal blocks every admin
        scenario, so seed() must cover it too."""
        from main.app.domain.user.auth.consent.models import (
            REQUIRED_SIGNUP_CONSENTS,
            UserConsent,
        )

        added = await self._seed_adds()
        admin_consents = {
            c.document_type
            for c in added
            if isinstance(c, UserConsent) and c.user_id == SUPER_ADMIN_ID
        }
        assert admin_consents == {t.value for t in REQUIRED_SIGNUP_CONSENTS}

    async def test_seeded_consents_are_timestamped(self):
        from main.app.domain.user.auth.consent.models import UserConsent

        added = await self._seed_adds()
        consents = [c for c in added if isinstance(c, UserConsent)]
        assert consents and all(c.accepted_at is not None for c in consents)


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

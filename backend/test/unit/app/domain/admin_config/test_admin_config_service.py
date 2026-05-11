"""Unit tests for AdminConfigService — get/set/seed defaults.

Covers:
- get() returns hardcoded default when row is absent
- get() returns stored value when row is present
- get_int() parses integer; falls back on bad value
- get_bool() parses truthy strings; falls back on bad value
- set() creates a new row when key is absent
- set() updates existing row when key is present
- get_all() merges stored rows with CONFIG_DEFAULTS entries
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.domain.admin_config.models import AdminConfigDto, AdminConfig
from main.app.domain.admin_config.service import AdminConfigService, CONFIG_DEFAULTS
from main.appodus_utils.db.session import db_session_ctx


# ── fixtures ──────────────────────────────────────────────────────────────────

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


def _make_row(key: str, value: str) -> AdminConfig:
    row = MagicMock(spec=AdminConfig)
    row.id = "row-id-1"
    row.key = key
    row.value = value
    row.description = "test"
    row.updated_by = None
    row.date_updated = datetime(2026, 5, 1, tzinfo=timezone.utc)
    return row


def _make_service(get_by_key=None, list_all=None, create=None, update=None):
    repo = MagicMock()
    repo.get_by_key = AsyncMock(return_value=get_by_key)
    repo.list_all = AsyncMock(return_value=list_all or [])
    repo.create = AsyncMock()
    repo.create_return_model = AsyncMock()
    repo.update = AsyncMock()
    return AdminConfigService(repo=repo)


# ── get() ──────────────────────────────────────────────────────────────────────

class TestGet:
    async def test_returns_default_when_absent(self):
        svc = _make_service(get_by_key=None)
        value = await svc.get("no_show_timeout_hours")
        assert value == CONFIG_DEFAULTS["no_show_timeout_hours"][0]

    async def test_returns_stored_value(self):
        row = _make_row("no_show_timeout_hours", "8")
        svc = _make_service(get_by_key=row)
        value = await svc.get("no_show_timeout_hours")
        assert value == "8"

    async def test_unknown_key_returns_empty_string(self):
        svc = _make_service(get_by_key=None)
        value = await svc.get("totally_unknown_key")
        assert value == ""


# ── get_int() ─────────────────────────────────────────────────────────────────

class TestGetInt:
    async def test_parses_integer(self):
        row = _make_row("no_show_timeout_hours", "12")
        svc = _make_service(get_by_key=row)
        assert await svc.get_int("no_show_timeout_hours") == 12

    async def test_fallback_on_non_numeric(self):
        row = _make_row("no_show_timeout_hours", "not-a-number")
        svc = _make_service(get_by_key=row)
        assert await svc.get_int("no_show_timeout_hours", fallback=99) == 99

    async def test_default_fallback_is_zero(self):
        row = _make_row("bad_key", "bad")
        svc = _make_service(get_by_key=row)
        assert await svc.get_int("bad_key") == 0


# ── get_bool() ────────────────────────────────────────────────────────────────

class TestGetBool:
    @pytest.mark.parametrize("raw", ["true", "True", "TRUE", "1", "yes"])
    async def test_truthy_strings(self, raw):
        row = _make_row("auto_assignment_enabled", raw)
        svc = _make_service(get_by_key=row)
        assert await svc.get_bool("auto_assignment_enabled") is True

    @pytest.mark.parametrize("raw", ["false", "False", "FALSE", "0", "no", ""])
    async def test_falsy_strings(self, raw):
        row = _make_row("auto_assignment_enabled", raw)
        svc = _make_service(get_by_key=row)
        assert await svc.get_bool("auto_assignment_enabled") is False

    async def test_default_for_auto_assignment_is_true(self):
        svc = _make_service(get_by_key=None)
        # CONFIG_DEFAULTS has "true" for auto_assignment_enabled
        assert await svc.get_bool("auto_assignment_enabled") is True


# ── set() ─────────────────────────────────────────────────────────────────────

class TestSet:
    async def test_creates_row_when_absent(self):
        repo = MagicMock()
        repo.get_by_key = AsyncMock(side_effect=[None, _make_row("no_show_timeout_hours", "6")])
        repo.create = AsyncMock()
        repo.create_return_model = AsyncMock()
        repo.update = AsyncMock()
        svc = AdminConfigService(repo=repo)

        result = await svc.set("no_show_timeout_hours", "6", "admin-1")
        repo.create.assert_awaited_once()
        assert result.value == "6"

    async def test_updates_existing_row(self):
        existing = _make_row("no_show_timeout_hours", "4")
        updated = _make_row("no_show_timeout_hours", "8")
        repo = MagicMock()
        repo.get_by_key = AsyncMock(side_effect=[existing, updated])
        repo.create = AsyncMock()
        repo.update = AsyncMock()
        svc = AdminConfigService(repo=repo)

        result = await svc.set("no_show_timeout_hours", "8", "admin-1")
        repo.update.assert_awaited_once()
        assert result.value == "8"


# ── get_all() ─────────────────────────────────────────────────────────────────

class TestGetAll:
    async def test_returns_all_default_keys_when_no_stored_rows(self):
        svc = _make_service(list_all=[])
        all_items = await svc.get_all()
        keys = {item.key for item in all_items}
        assert keys == set(CONFIG_DEFAULTS.keys())

    async def test_uses_stored_value_over_default(self):
        row = _make_row("no_show_timeout_hours", "99")
        svc = _make_service(list_all=[row])
        all_items = await svc.get_all()
        timeout = next(i for i in all_items if i.key == "no_show_timeout_hours")
        assert timeout.value == "99"

    async def test_fills_missing_keys_with_defaults(self):
        row = _make_row("no_show_timeout_hours", "4")
        svc = _make_service(list_all=[row])
        all_items = await svc.get_all()
        pool = next(i for i in all_items if i.key == "pool_timeout_hours")
        assert pool.value == CONFIG_DEFAULTS["pool_timeout_hours"][0]

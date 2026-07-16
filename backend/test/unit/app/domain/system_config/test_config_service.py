"""ConfigService (§14/§18.5, D28): typed accessors with default fallback + coercion on set."""
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.domain.system_config.models import CONFIG_DEFAULTS, ConfigKey
from main.app.domain.system_config.service import ConfigService
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


def _service(stored=None):
    svc = object.__new__(ConfigService)
    svc._config_repo = MagicMock()
    svc._audit = MagicMock()
    svc._audit.schedule = MagicMock()
    rows = stored or {}
    svc._config_repo.get_by_key = AsyncMock(side_effect=lambda k: rows.get(k))
    svc._config_repo.create = AsyncMock()
    svc._config_repo.create_return_model = AsyncMock(
        return_value=SimpleNamespace(id="c-1", value_json=30)
    )
    svc._config_repo.update = AsyncMock()
    svc._config_repo.get_model = AsyncMock(return_value=SimpleNamespace(id="c-1", value_json=45))
    return svc, rows


class TestGet:
    async def test_get_int_falls_back_to_default(self):
        svc, _ = _service()
        assert await svc.get_int(ConfigKey.DISPUTE_WINDOW_DAYS) == CONFIG_DEFAULTS[ConfigKey.DISPUTE_WINDOW_DAYS]

    async def test_get_int_reads_stored_row(self):
        svc, _ = _service({ConfigKey.RECHECK_PRICE_PCT.value: SimpleNamespace(value_json=25)})
        assert await svc.get_int(ConfigKey.RECHECK_PRICE_PCT) == 25


class TestSet:
    async def test_set_coerces_to_int(self):
        svc, _ = _service()
        await svc.set(ConfigKey.DISPUTE_WINDOW_DAYS, "45", "admin-1")
        # create_return_model called with a coerced int value
        dto = svc._config_repo.create_return_model.await_args.args[0]
        assert dto.value_json == 45 and isinstance(dto.value_json, int)

    async def test_set_audits(self):
        svc, _ = _service()
        await svc.set(ConfigKey.DISPUTE_WINDOW_DAYS, 20, "admin-1")
        svc._audit.schedule.assert_called_once()


"""ConfigService (§14/§18.5, D28): typed accessors with default fallback + coercion on set."""
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.domain.system_config.models import CONFIG_DEFAULTS, ConfigKey
from main.app.domain.system_config.service import ConfigService
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


def _service(stored=None):
    svc = object.__new__(ConfigService)
    svc._config_repo = MagicMock()
    svc._audit = MagicMock()
    svc._audit.schedule = MagicMock()
    svc._margin_guard = AsyncMock()
    rows = stored or {}
    svc._config_repo.get_by_key = AsyncMock(side_effect=lambda k: rows.get(k))
    svc._config_repo.create = AsyncMock()
    svc._config_repo.create_return_model = AsyncMock(
        return_value=SimpleNamespace(id="c-1", value_json=30)
    )
    svc._config_repo.upsert = AsyncMock(side_effect=lambda values, update_columns, **kw: SimpleNamespace(
        id="c-1", **values))
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
        # One upsert on the live key, with the value coerced to the default's type.
        values, update_columns = svc._config_repo.upsert.await_args.args
        assert values["value_json"] == 45 and isinstance(values["value_json"], int)
        assert update_columns == ["value_json"]
        assert svc._config_repo.upsert.await_args.kwargs == {"unique_index": "uq_system_config_key"}

    async def test_set_audits(self):
        svc, _ = _service()
        await svc.set(ConfigKey.DISPUTE_WINDOW_DAYS, 20, "admin-1")
        svc._audit.schedule.assert_called_once()


class TestMinimumMargin:
    """The commission margin is guarded where it is set, like the prices and commissions it
    constrains (§20.1 / D97)."""

    async def test_a_new_minimum_margin_is_checked_before_it_is_stored(self):
        svc, _ = _service()
        await svc.set(ConfigKey.COMMISSION_MIN_MARGIN_PCT, "40", "admin-1")
        svc._margin_guard.check.assert_awaited_once_with(min_margin_pct=40)
        assert svc._config_repo.upsert.await_args.args[0]["value_json"] == 40

    async def test_a_margin_the_current_configuration_cannot_meet_is_refused(self):
        svc, _ = _service()
        svc._margin_guard.check = AsyncMock(side_effect=ValidationException(message="below the margin"))
        with pytest.raises(ValidationException):
            await svc.set(ConfigKey.COMMISSION_MIN_MARGIN_PCT, 90, "admin-1")
        svc._config_repo.upsert.assert_not_awaited()

    @pytest.mark.parametrize("value", [-1, 101])
    async def test_a_margin_outside_0_to_100_is_refused(self, value):
        svc, _ = _service()
        with pytest.raises(ValidationException):
            await svc.set(ConfigKey.COMMISSION_MIN_MARGIN_PCT, value, "admin-1")
        svc._margin_guard.check.assert_not_awaited()

    async def test_other_keys_do_not_consult_the_margin_guard(self):
        svc, _ = _service()
        await svc.set(ConfigKey.DISPUTE_WINDOW_DAYS, 20, "admin-1")
        svc._margin_guard.check.assert_not_awaited()


class TestRemoteBonus:
    """The remote bonus is a guarded write like the margin itself (§20.1 / D97)."""

    async def test_a_new_bonus_is_checked_against_the_margin_before_it_is_stored(self):
        svc, _ = _service()
        await svc.set(ConfigKey.REMOTE_JOB_BONUS_NGN_KOBO, "500000", "admin-1")
        svc._margin_guard.check.assert_awaited_once_with(remote_bonus_minor=500_000)
        assert svc._config_repo.upsert.await_args.args[0]["value_json"] == 500_000

    async def test_a_negative_bonus_is_refused_without_consulting_the_guard(self):
        svc, _ = _service()
        with pytest.raises(ValidationException):
            await svc.set(ConfigKey.REMOTE_JOB_BONUS_NGN_KOBO, -1, "admin-1")
        svc._margin_guard.check.assert_not_awaited()
        svc._config_repo.upsert.assert_not_awaited()

    async def test_a_bonus_that_breaks_the_margin_is_never_stored(self):
        svc, _ = _service()
        svc._margin_guard.check = AsyncMock(side_effect=ValidationException(message="below the margin"))
        with pytest.raises(ValidationException):
            await svc.set(ConfigKey.REMOTE_JOB_BONUS_NGN_KOBO, 9_000_000, "admin-1")
        svc._config_repo.upsert.assert_not_awaited()

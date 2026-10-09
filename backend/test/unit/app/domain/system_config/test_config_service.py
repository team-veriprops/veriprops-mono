"""ConfigService (§14/§18.5, D28): typed accessors with default fallback + coercion on set."""
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.domain.system_config.models import CONFIG_DEFAULTS, ConfigKey, ConfigUnit
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


class TestDiscounts:
    """A discount lowers what a case collects while its agents are still paid in full, so both
    discount percentages are guarded writes like the margin itself (§17.1, §20.1 / D97)."""

    @pytest.mark.parametrize("key, override", [
        (ConfigKey.FIRST_TIME_DISCOUNT_PERCENT, "first_time_pct"),
        (ConfigKey.MAX_DISCOUNT_PERCENT, "max_discount_pct"),
    ])
    async def test_a_new_discount_is_checked_against_the_margin_before_it_is_stored(self, key, override):
        svc, _ = _service()
        await svc.set(key, "15", "admin-1")
        svc._margin_guard.check.assert_awaited_once_with(**{override: 15})
        assert svc._config_repo.upsert.await_args.args[0]["value_json"] == 15

    @pytest.mark.parametrize("key", [ConfigKey.FIRST_TIME_DISCOUNT_PERCENT, ConfigKey.MAX_DISCOUNT_PERCENT])
    @pytest.mark.parametrize("value", [-1, 101])
    async def test_a_discount_outside_0_to_100_is_refused(self, key, value):
        svc, _ = _service()
        with pytest.raises(ValidationException):
            await svc.set(key, value, "admin-1")
        svc._margin_guard.check.assert_not_awaited()
        svc._config_repo.upsert.assert_not_awaited()

    async def test_a_discount_that_breaks_the_margin_is_never_stored(self):
        svc, _ = _service()
        svc._margin_guard.check = AsyncMock(side_effect=ValidationException(message="below the margin"))
        with pytest.raises(ValidationException):
            await svc.set(ConfigKey.MAX_DISCOUNT_PERCENT, 80, "admin-1")
        svc._config_repo.upsert.assert_not_awaited()


class TestUnits:
    """Each key declares its unit so the admin screen can show money in naira while the store
    keeps kobo — the backend, not the page, knows which keys are money."""

    async def test_the_remote_bonus_is_declared_in_minor_currency(self):
        svc, _ = _service()
        svc._config_repo.list_all = AsyncMock(return_value=[])
        units = {item.key: item.unit for item in await svc.list_all()}
        assert units[ConfigKey.REMOTE_JOB_BONUS_NGN_KOBO] == ConfigUnit.MINOR_CURRENCY
        assert units[ConfigKey.REFERRAL_CREDIT_NGN] == ConfigUnit.MAJOR_CURRENCY
        assert units[ConfigKey.MAX_DISCOUNT_PERCENT] == ConfigUnit.PERCENT
        assert units[ConfigKey.DISPUTE_WINDOW_DAYS] is None

    async def test_the_code_owned_description_wins_over_the_seeded_copy(self):
        # Migration 0001 seeded each row with the description of its day ("…, in kobo, …"); the
        # admin types naira now, so the stale copy must not be what they read.
        svc, _ = _service()
        svc._config_repo.list_all = AsyncMock(return_value=[SimpleNamespace(
            key=ConfigKey.REMOTE_JOB_BONUS_NGN_KOBO.value, value_json=0,
            description="Flat bonus, in kobo, paid …", date_updated=None,
        )])
        bonus = next(i for i in await svc.list_all() if i.key == ConfigKey.REMOTE_JOB_BONUS_NGN_KOBO)
        assert "kobo" not in bonus.description

    async def test_a_row_holding_no_value_lists_the_default_that_readers_use(self):
        # The list shows what every reader of the key gets (`effective_config_value`), so a row
        # with a null value shows the default, not a blank.
        svc, _ = _service()
        svc._config_repo.list_all = AsyncMock(return_value=[SimpleNamespace(
            key=ConfigKey.DISPUTE_WINDOW_DAYS.value, value_json=None, description=None, date_updated=None,
        )])
        window = next(i for i in await svc.list_all() if i.key == ConfigKey.DISPUTE_WINDOW_DAYS)
        assert window.value == CONFIG_DEFAULTS[ConfigKey.DISPUTE_WINDOW_DAYS]

    async def test_the_unit_travels_as_camel_case(self):
        svc, _ = _service()
        svc._config_repo.list_all = AsyncMock(return_value=[])
        bonus = next(i for i in await svc.list_all() if i.key == ConfigKey.REMOTE_JOB_BONUS_NGN_KOBO)
        assert bonus.model_dump(by_alias=True, mode="json")["unit"] == "MINOR_CURRENCY"

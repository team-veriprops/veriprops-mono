"""Human coverage hours (Decision G, §26.6.2, D68).

The escalation copy makes a promise, and this service decides which promise. Both
directions cost trust: an unstaffed "a team member is joining" reads as a lie, and a
needless "we'll reply within 12 hours" sends away a customer whose console was staffed.

The clock is West Africa Time, so the boundaries are tested in WAT and in UTC — a naive
implementation passes the first and fails the second, and the customer's 8pm is the one
that matters.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.domain.channel.whatsapp.bot.support_hours import (
    WAT,
    CoverageState,
    SupportHoursService,
)
from main.app.domain.system_config.models import CONFIG_DEFAULTS, ConfigKey
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


def _service() -> SupportHoursService:
    """Reads the seeded defaults — 8am–8pm weekdays, Saturday to 1pm, no Sunday."""
    service = object.__new__(SupportHoursService)
    config = MagicMock()
    config.get_int = AsyncMock(side_effect=lambda key: CONFIG_DEFAULTS[key])
    service._config_service = config
    return service


def _wat(year, month, day, hour) -> datetime:
    return datetime(year, month, day, hour, tzinfo=WAT)


@pytest.mark.parametrize(
    "moment, expected",
    [
        # Tuesday 2026-09-01
        (_wat(2026, 9, 1, 7), CoverageState.CLOSED),   # an hour before opening
        (_wat(2026, 9, 1, 8), CoverageState.OPEN),     # the first staffed hour counts
        (_wat(2026, 9, 1, 14), CoverageState.OPEN),
        (_wat(2026, 9, 1, 19), CoverageState.OPEN),    # the last hour is still cover
        (_wat(2026, 9, 1, 20), CoverageState.CLOSED),  # 8pm is the close, not an hour of it
        (_wat(2026, 9, 1, 23), CoverageState.CLOSED),
    ],
    ids=["before-open", "opening-hour", "midday", "last-hour", "closing-hour", "night"],
)
async def test_weekday_window(moment, expected):
    assert (await _service().coverage(moment)).state == expected


@pytest.mark.parametrize(
    "moment, expected",
    [
        # Saturday 2026-09-05 — morning cover only.
        (_wat(2026, 9, 5, 9), CoverageState.OPEN),
        (_wat(2026, 9, 5, 12), CoverageState.OPEN),
        (_wat(2026, 9, 5, 13), CoverageState.CLOSED),
        (_wat(2026, 9, 5, 18), CoverageState.CLOSED),
    ],
    ids=["saturday-morning", "saturday-noon", "saturday-close", "saturday-evening"],
)
async def test_saturday_closes_early(moment, expected):
    assert (await _service().coverage(moment)).state == expected


@pytest.mark.parametrize("hour", [9, 12, 15, 19], ids=lambda h: f"{h}h")
async def test_there_is_no_sunday_cover(hour):
    # Sunday 2026-09-06
    coverage = await _service().coverage(_wat(2026, 9, 6, hour))

    assert coverage.state == CoverageState.CLOSED


async def test_the_clock_is_the_customers_not_the_servers():
    """19:00 UTC is 20:00 in Lagos — closed. A naive UTC implementation would call this
    open and promise someone a colleague who has gone home."""
    utc_1900 = datetime(2026, 9, 1, 19, tzinfo=timezone.utc)

    assert (await _service().coverage(utc_1900)).state == CoverageState.CLOSED


async def test_an_early_utc_hour_is_already_open_in_lagos():
    """07:30 UTC is 08:30 WAT — the console is staffed."""
    utc_0730 = datetime(2026, 9, 1, 7, 30, tzinfo=timezone.utc)

    assert (await _service().coverage(utc_0730)).state == CoverageState.OPEN


async def test_the_offline_response_window_comes_from_config():
    """D68 — a rota or SLA change is an ops decision, not a redeploy."""
    coverage = await _service().coverage(_wat(2026, 9, 6, 12))

    assert coverage.response_hours == CONFIG_DEFAULTS[ConfigKey.OFFLINE_RESPONSE_HOURS]

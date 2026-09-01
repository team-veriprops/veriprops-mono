"""Human coverage hours (PRD Decision G, §7.6.2, D68).

Decision G buys 8am–8pm WAT on weekdays plus Saturday morning. §7.6.2 makes that a
promise the bot has to keep in words: inside the window an escalation says "a team member
is joining"; outside it states a response time. Getting that wrong in either direction is
a trust cost — an unstaffed "joining now" reads as a lie, and a needless "we'll reply
tomorrow" sends a customer away from a console that was staffed.

The hours are `system_config` keys, not constants (D68): a rota change is an ops
decision, and putting a redeploy between the founder and the rota would guarantee the
copy goes stale.

The clock is **West Africa Time**, fixed at UTC+1. Nigeria observes no daylight saving,
so a fixed offset is exact rather than an approximation — and it is the customer's own
wall clock, which is the only one an "8pm" promise can sensibly mean.
"""
from __future__ import annotations

import enum
from datetime import datetime, timedelta, timezone
from typing import NamedTuple

from kink import inject

from main.app.domain.system_config.models import ConfigKey
from main.app.domain.system_config.service import ConfigService
from main.appodus_utils import Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger

# West Africa Time. Not a setting: Nigeria has no DST and the number is a fact, so a
# configurable offset could only ever be configured wrong.
WAT = timezone(timedelta(hours=1))

_SATURDAY = 5
_SUNDAY = 6


class CoverageState(str, enum.Enum):
    """Whether a person is on the console right now."""

    OPEN = "OPEN"
    CLOSED = "CLOSED"


class Coverage(NamedTuple):
    """The answer the escalation copy needs: are we open, and if not, by when do we reply."""

    state: CoverageState
    response_hours: int

    @property
    def is_open(self) -> bool:
        return self.state == CoverageState.OPEN


@inject
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class SupportHoursService:
    def __init__(self, config_service: ConfigService):
        self._config_service = config_service

    async def coverage(self, at: datetime = None) -> Coverage:
        """Whether the console is staffed at *at* (defaults to now)."""
        moment = (at or Utils.datetime_now()).astimezone(WAT)
        start = await self._config_service.get_int(ConfigKey.SUPPORT_HOURS_START)
        end = await self._config_service.get_int(ConfigKey.SUPPORT_HOURS_END)
        saturday_end = await self._config_service.get_int(
            ConfigKey.SUPPORT_SATURDAY_END
        )
        response_hours = await self._config_service.get_int(
            ConfigKey.OFFLINE_RESPONSE_HOURS
        )

        closing = self._closing_hour(moment.weekday(), end, saturday_end)
        open_now = closing is not None and start <= moment.hour < closing
        return Coverage(
            state=CoverageState.OPEN if open_now else CoverageState.CLOSED,
            response_hours=response_hours,
        )

    @staticmethod
    def _closing_hour(weekday: int, weekday_end: int, saturday_end: int):
        """When cover ends on this day, or ``None`` when there is none at all."""
        if weekday == _SUNDAY:
            return None
        if weekday == _SATURDAY:
            return saturday_end
        return weekday_end

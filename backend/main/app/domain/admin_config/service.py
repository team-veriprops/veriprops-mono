"""Admin config service — get/set operational knobs."""
from __future__ import annotations

from typing import List

from kink import inject

from main.app.domain.admin_config.models import (
    AdminConfig,
    AdminConfigDto,
    CreateAdminConfigDto,
    UpdateAdminConfigDto,
)
from main.app.domain.admin_config.repo import AdminConfigRepo
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional

# Known keys with (default_value, description)
CONFIG_DEFAULTS: dict[str, tuple[str, str]] = {
    "no_show_timeout_hours": (
        "4",
        "Hours after task acceptance with no evidence upload before admin no-show alert fires",
    ),
    "pool_timeout_hours": (
        "24",
        "Hours a PENDING task stays unclaimed before admin pool-timeout alert fires",
    ),
    "auto_assignment_enabled": (
        "true",
        "When true, tasks are auto-created and broadcast to qualifying agents when a verification reaches PAID",
    ),
    # Phase 16 — Agent Reputation & Coverage
    "agent_max_active_tasks": (
        "5",
        "Max concurrent active tasks (ACCEPTED+IN_PROGRESS) before agent is auto-set to UNAVAILABLE",
    ),
    "agent_low_performance_threshold": (
        "60",
        "Completion rate % below which an agent receives reduced job feed visibility",
    ),
    "agent_top_agent_accuracy_threshold": (
        "4.5",
        "Accuracy score (1–5) at or above which an agent earns the Top Agent badge",
    ),
    "task_sla_hours": (
        "48",
        "Hours from task acceptance within which submission is counted as on-time for timeliness score",
    ),
    # Phase 17 — Growth & Conversion
    "referral_credit_ngn": (
        "1000",
        "Credit amount (NGN) added to a referrer when their invitee completes their first payment",
    ),
    "first_time_discount_percent": (
        "10",
        "Percentage discount auto-applied to a customer's first verification payment",
    ),
    "max_discount_percent": (
        "20",
        "Maximum combined discount cap (referral + first-time) applied to any single payment",
    ),
}


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class AdminConfigService:
    def __init__(self, repo: AdminConfigRepo):
        self._repo = repo

    async def get(self, key: str) -> str:
        """Return the stored value, or the default if the key has never been set."""
        row = await self._repo.get_by_key(key)
        if row is not None:
            return row.value
        default, _ = CONFIG_DEFAULTS.get(key, ("", ""))
        return default

    async def get_int(self, key: str, fallback: int = 0) -> int:
        raw = await self.get(key)
        try:
            return int(raw)
        except (ValueError, TypeError):
            return fallback

    async def get_bool(self, key: str, fallback: bool = True) -> bool:
        raw = await self.get(key)
        return raw.lower() in ("true", "1", "yes")

    async def get_all(self) -> List[AdminConfigDto]:
        rows_by_key = {r.key: r for r in await self._repo.list_all()}
        out: List[AdminConfigDto] = []
        for key, (default_val, desc) in CONFIG_DEFAULTS.items():
            if key in rows_by_key:
                out.append(self._to_dto(rows_by_key[key]))
            else:
                out.append(AdminConfigDto(
                    id="",
                    key=key,
                    value=default_val,
                    description=desc,
                    updated_by=None,
                    date_updated=None,
                ))
        return out

    async def set(self, key: str, value: str, updated_by: str) -> AdminConfigDto:
        row = await self._repo.get_by_key(key)
        if row is None:
            _, desc = CONFIG_DEFAULTS.get(key, ("", ""))
            await self._repo.create(CreateAdminConfigDto(
                key=key,
                value=value,
                description=desc or None,
                updated_by=updated_by,
            ))
            row = await self._repo.get_by_key(key)
        else:
            await self._repo.update(str(row.id), UpdateAdminConfigDto(
                value=value,
                updated_by=updated_by,
            ))
            row = await self._repo.get_by_key(key)
        return self._to_dto(row)

    @staticmethod
    def _to_dto(row: AdminConfig) -> AdminConfigDto:
        return AdminConfigDto(
            id=str(row.id),
            key=row.key,
            value=row.value,
            description=row.description,
            updated_by=row.updated_by,
            date_updated=row.date_updated,
        )

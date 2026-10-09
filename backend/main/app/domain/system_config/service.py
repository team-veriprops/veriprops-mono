"""System configuration service (PRD §14, §18.5 / D28).

Typed accessors over an admin-editable key-value store. Default rows are seeded by
migration 0001 from ``CONFIG_DEFAULTS``; reads fall back to those defaults, so a
missing row never breaks a caller.
"""
from __future__ import annotations

from typing import Any, List

from kink import inject

from main.app.domain.audit.models import AuditActionType
from main.app.domain.audit.service import AuditLogService
from main.app.domain.commission_rule.margin import CommissionMarginGuard
from main.app.domain.system_config.models import (
    CONFIG_DEFAULTS,
    CONFIG_DESCRIPTIONS,
    CONFIG_UNITS,
    ConfigKey,
    CreateSystemConfigDto,
    SystemConfig,
    SystemConfigDto,
    effective_config_value,
)
from main.app.domain.system_config.repo import SystemConfigRepo
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import ValidationException


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class ConfigService:
    def __init__(
        self,
        config_repo: SystemConfigRepo,
        audit_service: AuditLogService,
        commission_margin_guard: CommissionMarginGuard,
    ):
        self._config_repo = config_repo
        self._audit = audit_service
        self._margin_guard = commission_margin_guard

    async def get_int(self, key: ConfigKey) -> int:
        raw = await self._raw(key)
        return int(raw)

    async def get_bool(self, key: ConfigKey) -> bool:
        raw = await self._raw(key)
        return bool(raw)

    async def get_str(self, key: ConfigKey) -> str:
        return str(await self._raw(key))

    async def set(self, key: ConfigKey, value: Any, admin_id: str) -> SystemConfig:
        """Update (or create) a config value, coercing to the default's type. The four keys the
        commission margin reads — the minimum margin, the remote bonus and the two discount
        percentages — must leave every tier its margin at the current prices and commissions
        (§20.1 / D97)."""
        coerced = self._coerce(key, value)
        if key == ConfigKey.COMMISSION_MIN_MARGIN_PCT:
            self._require_percent(coerced, "The minimum margin")
            await self._margin_guard.check(min_margin_pct=coerced)
        elif key == ConfigKey.REMOTE_JOB_BONUS_NGN_KOBO:
            if coerced < 0:
                raise ValidationException(message="The remote bonus cannot be negative.")
            await self._margin_guard.check(remote_bonus_minor=coerced)
        elif key == ConfigKey.FIRST_TIME_DISCOUNT_PERCENT:
            self._require_percent(coerced, "The first-time discount")
            await self._margin_guard.check(first_time_pct=coerced)
        elif key == ConfigKey.MAX_DISCOUNT_PERCENT:
            self._require_percent(coerced, "The discount cap")
            await self._margin_guard.check(max_discount_pct=coerced)
        row = await self._config_repo.upsert(
            CreateSystemConfigDto(
                key=key.value, value_json=coerced, description=CONFIG_DESCRIPTIONS.get(key),
            ).model_dump(by_alias=False),
            ["value_json"],
            unique_index="uq_system_config_key",
        )
        self._audit.schedule(
            action=AuditActionType.ADMIN_CONFIG_CHANGED,
            resource_type="system_config", resource_id=row.id, actor_id=admin_id,
            details={"key": key.value, "value": coerced},
        )
        return row

    async def list_all(self) -> List[SystemConfigDto]:
        """Every known key at its effective value (stored row, else default), with its unit.
        The description is code-owned: the copy seeded on a row goes stale as the rule it
        describes changes, so the row's is only a fallback for a key with none in code."""
        stored = {c.key: c for c in await self._config_repo.list_all()}
        out: List[SystemConfigDto] = []
        for key in ConfigKey:
            row = stored.get(key.value)
            out.append(SystemConfigDto(
                key=key,
                value=effective_config_value(row.value_json if row is not None else None, key),
                unit=CONFIG_UNITS.get(key),
                description=CONFIG_DESCRIPTIONS.get(key) or (row.description if row is not None else None),
                date_updated=row.date_updated if row is not None else None,
            ))
        return out

    # ── helpers ───────────────────────────────────────────────────

    async def _raw(self, key: ConfigKey) -> Any:
        row = await self._config_repo.get_by_key(key.value)
        return effective_config_value(row.value_json if row is not None else None, key)

    @staticmethod
    def _require_percent(value: int, what: str) -> None:
        if not 0 <= value <= 100:
            raise ValidationException(message=f"{what} must be between 0 and 100%.")

    def _coerce(self, key: ConfigKey, value: Any) -> Any:
        default = CONFIG_DEFAULTS[key]
        try:
            if isinstance(default, bool):
                return bool(value)
            if isinstance(default, int):
                return int(value)
            return value
        except (TypeError, ValueError):
            raise ValidationException(message=f"Invalid value for {key.value}.")

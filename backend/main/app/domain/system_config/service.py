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
from main.app.domain.system_config.models import (
    CONFIG_DEFAULTS,
    CONFIG_DESCRIPTIONS,
    ConfigKey,
    CreateSystemConfigDto,
    SystemConfig,
    SystemConfigDto,
    UpdateSystemConfigDto,
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
    def __init__(self, config_repo: SystemConfigRepo, audit_service: AuditLogService):
        self._config_repo = config_repo
        self._audit = audit_service

    async def get_int(self, key: ConfigKey) -> int:
        raw = await self._raw(key)
        return int(raw)

    async def get_bool(self, key: ConfigKey) -> bool:
        raw = await self._raw(key)
        return bool(raw)

    async def get_str(self, key: ConfigKey) -> str:
        return str(await self._raw(key))

    async def set(self, key: ConfigKey, value: Any, admin_id: str) -> SystemConfig:
        """Update (or create) a config value, coercing to the default's type."""
        coerced = self._coerce(key, value)
        existing = await self._config_repo.get_by_key(key.value)
        if existing is None:
            row = await self._config_repo.create_return_model(CreateSystemConfigDto(
                key=key.value, value_json=coerced, description=CONFIG_DESCRIPTIONS.get(key),
            ))
        else:
            await self._config_repo.update(existing.id, UpdateSystemConfigDto(value_json=coerced))
            row = await self._config_repo.get_model(existing.id)
        self._audit.schedule(
            action=AuditActionType.ADMIN_CONFIG_CHANGED,
            resource_type="system_config", resource_id=row.id, actor_id=admin_id,
            details={"key": key.value, "value": coerced},
        )
        return row

    async def list_all(self) -> List[SystemConfigDto]:
        """Every known key at its effective value (stored row, else default)."""
        stored = {c.key: c for c in await self._config_repo.list_all()}
        out: List[SystemConfigDto] = []
        for key in ConfigKey:
            row = stored.get(key.value)
            out.append(SystemConfigDto(
                key=key,
                value=row.value_json if row is not None else CONFIG_DEFAULTS.get(key),
                description=(row.description if row is not None else None) or CONFIG_DESCRIPTIONS.get(key),
                date_updated=row.date_updated if row is not None else None,
            ))
        return out

    # ── helpers ───────────────────────────────────────────────────

    async def _raw(self, key: ConfigKey) -> Any:
        row = await self._config_repo.get_by_key(key.value)
        if row is not None and row.value_json is not None:
            return row.value_json
        return CONFIG_DEFAULTS[key]

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

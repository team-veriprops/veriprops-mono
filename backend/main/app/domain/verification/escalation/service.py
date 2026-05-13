"""Escalation service — agent issue reporting + admin SSE alert (S27)."""
from __future__ import annotations

from typing import List, TYPE_CHECKING

from kink import di, inject

from main.app.domain.verification.escalation.models import (
    CreateEscalationDto,
    Escalation,
    EscalationCategory,
    EscalationDto,
    ReportEscalationDto,
)
from main.app.domain.verification.escalation.repo import EscalationRepo
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional

if TYPE_CHECKING:
    from loguru import Logger

logger: "Logger" = di["logger"]


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class EscalationService:
    def __init__(self, repo: EscalationRepo):
        self._repo = repo

    async def report(
        self, task_id: str, reporter_id: str, dto: ReportEscalationDto,
    ) -> EscalationDto:
        escalation = await self._repo.create_return_model(
            CreateEscalationDto(
                task_id=task_id,
                reporter_id=reporter_id,
                category=dto.category,
                description=dto.description,
            )
        )
        # Fire SSE event to admin channel
        try:
            from main.appodus_utils.db.redis_utils import RedisUtils
            redis: RedisUtils = di[RedisUtils]
            await redis.publish(
                "admin:escalations",
                {
                    "event": "ESCALATION_CREATED",
                    "task_id": task_id,
                    "reporter_id": reporter_id,
                    "category": dto.category.value,
                    "escalation_id": str(escalation.id),
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"SSE publish failed for escalation {escalation.id}: {exc}")
        return self._to_dto(escalation)

    async def list_for_task(self, task_id: str) -> List[EscalationDto]:
        items = await self._repo.list_for_task(task_id)
        return [self._to_dto(i) for i in items]

    @staticmethod
    def _to_dto(item: Escalation) -> EscalationDto:
        return EscalationDto(
            id=str(item.id),
            task_id=item.task_id,
            reporter_id=item.reporter_id,
            category=EscalationCategory(item.category),
            description=item.description,
            date_created=item.date_created,
            date_updated=item.date_updated,
        )

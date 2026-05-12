"""Fraud detection service (S38)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import List, Optional, TYPE_CHECKING

from kink import inject

from main.app.domain.thread.fraud import rules as _rules
from main.app.domain.thread.fraud.models import (
    CreateFraudFlagDto,
    FraudFlagDto,
    FraudReviewDecision,
    ReviewFraudFlagDto,
    UpdateFraudFlagDto,
)
from main.app.domain.thread.fraud.repo import FraudFlagRepo
from main.app.domain.thread.models import UpdateThreadMessageDto
from main.app.domain.thread.repo import ThreadMessageRepo
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import ResourceNotFoundException

if TYPE_CHECKING:
    from loguru import Logger
from kink import di
logger: "Logger" = di["logger"]


@inject
@decorate_all_methods(transactional(), exclude=["__init__", "scan"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__", "scan"], exclude_startswith=["_"])
class FraudDetectionService:
    def __init__(
        self,
        flag_repo: FraudFlagRepo,
        message_repo: ThreadMessageRepo,
    ):
        self._flags = flag_repo
        self._messages = message_repo

    @staticmethod
    def scan(body: str) -> List[str]:
        return _rules.scan(body)

    async def record_flag(
        self,
        message_body: str,
        matched_patterns: List[str],
        message_id: Optional[str] = None,
    ) -> FraudFlagDto:
        flag = await self._flags.create_return_model(
            CreateFraudFlagDto(
                message_id=message_id or "",
                message_body=message_body,
                matched_patterns=json.dumps(matched_patterns),
            )
        )
        return self._to_dto(flag)

    async def list_pending(self) -> List[FraudFlagDto]:
        flags = await self._flags.list_pending()
        return [self._to_dto(f) for f in flags]

    async def review(self, flag_id: str, dto: ReviewFraudFlagDto, reviewer_id: str) -> FraudFlagDto:
        flag = await self._flags.get_model(flag_id)
        if flag is None:
            raise ResourceNotFoundException(resource="FraudFlag")

        await self._flags.update(
            flag_id,
            UpdateFraudFlagDto(
                reviewed=True,
                review_decision=dto.decision.value,
                reviewer_id=reviewer_id,
                reviewed_at=datetime.now(timezone.utc),
            ),
        )

        if dto.decision == FraudReviewDecision.APPROVED and flag.message_id:
            # Release the held message
            try:
                from main.app.domain.thread.service import ThreadService
                thread_svc: ThreadService = di[ThreadService]
                await thread_svc.release_held_message(flag.message_id)
            except Exception as exc:
                logger.warning("Could not release held message {}: {}", flag.message_id, exc)
        elif dto.decision == FraudReviewDecision.REJECTED and flag.message_id:
            try:
                from main.app.domain.thread.service import ThreadService
                thread_svc: ThreadService = di[ThreadService]
                await thread_svc.discard_held_message(flag.message_id)
            except Exception as exc:
                logger.warning("Could not discard held message {}: {}", flag.message_id, exc)

        flag = await self._flags.get_model(flag_id)
        return self._to_dto(flag)

    def _to_dto(self, row) -> FraudFlagDto:
        return FraudFlagDto(
            id=str(row.id),
            message_id=row.message_id,
            message_body=row.message_body,
            matched_patterns=json.loads(row.matched_patterns or "[]"),
            reviewed=row.reviewed,
            review_decision=FraudReviewDecision(row.review_decision) if row.review_decision else None,
            reviewer_id=row.reviewer_id,
            reviewed_at=row.reviewed_at,
            created_at=row.date_created,
        )

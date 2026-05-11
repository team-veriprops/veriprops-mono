"""Task review DTOs — admin approve/reject/reopen (S28)."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from main.appodus_utils import Object


class TaskReviewDecision(str, enum.Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ApproveTaskDto(Object):
    note: Optional[str] = None


class RejectTaskDto(Object):
    reason: str  # minimum 30 chars validated in service


class ReopenTaskDto(Object):
    reason: str  # minimum 30 chars validated in service


class TaskReviewDto(Object):
    task_id: str
    decision: TaskReviewDecision
    reason: Optional[str] = None
    reviewed_by: str
    reviewed_at: datetime

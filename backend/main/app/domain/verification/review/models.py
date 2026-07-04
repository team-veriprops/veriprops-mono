"""Admin review & release DTOs (PRD §8). Orchestration-only — no ORM entity."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from main.app.core.state.status import AgentRole, VerificationStatus, VerificationTier
from main.app.domain.verification.report.models import ReportDto
from main.app.domain.verification.task.models import TaskDto
from main.appodus_utils import Object


class ApproveTaskDto(Object):
    """Admin approves a role's submission with an optional quality score (0–100, §8.3)."""

    quality: int = 100


class RejectTaskDto(Object):
    reason: str


class ReleaseDto(Object):
    reason: Optional[str] = None


class FailVerificationDto(Object):
    reason: str


class ReviewConflictDto(Object):
    severity: str
    roles: List[AgentRole]
    message: str


class ReviewStateDto(Object):
    """The admin report-review surface: task grid + conflicts + score preview + report."""

    verification_id: str
    status: VerificationStatus
    tier: Optional[VerificationTier] = None
    tasks: List[TaskDto] = []
    conflicts: List[ReviewConflictDto] = []
    projected_trust_score: Optional[int] = None
    all_approved: bool = False
    releasable: bool = False
    report: Optional[ReportDto] = None
    findings: Dict[str, Any] = {}

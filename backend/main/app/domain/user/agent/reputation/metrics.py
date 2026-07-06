"""Pure agent reputation metrics (PRD §16.1, D32).

Derived on read from an agent's verification tasks — never stored, so a metric can't drift.
Accuracy reuses the per-task admin ``review_quality`` (0–100) presented on a 5-point scale;
timeliness compares each submission against ``task_sla_hours``; the composite blends them for
the assignment ranking. This module is arithmetic only, so it is trivially unit-testable.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Optional

from main.app.core.state.status import TaskState

# Composite weighting (§16.1): quality-heavy, with completion + timeliness contributing.
_W_COMPLETION = 0.35
_W_ACCURACY = 0.45
_W_TIMELINESS = 0.20
_DECLINE_PENALTY_PER = 3  # composite points shed per decline, capped
_MAX_DECLINE_PENALTY = 20


@dataclass(frozen=True)
class AgentMetrics:
    total_jobs: int          # tasks ever assigned
    completed_jobs: int      # tasks admin-approved
    completion_rate: int     # completed / taken-on, 0–100
    avg_quality: int         # mean review_quality of completed jobs, 0–100
    accuracy_score: float    # avg_quality on a 5-point scale (§16.1)
    timeliness_rate: int     # submissions within task_sla_hours, 0–100
    decline_count: int
    composite_score: int     # 0–100 ranking score
    active_since: Optional[datetime]


class _TaskLike:  # documentation of the duck-typed shape
    state: str
    review_quality: Optional[int]
    decline_count: Optional[int]
    accepted_at: Optional[datetime]
    submitted_at: Optional[datetime]
    date_created: Optional[datetime]


def compute_metrics(tasks: Iterable, task_sla_hours: int) -> AgentMetrics:
    tasks = list(tasks)
    total = len(tasks)
    taken = [t for t in tasks if t.accepted_at is not None]
    completed = [t for t in tasks if t.state == TaskState.APPROVED.value]

    completion_rate = _pct(len(completed), len(taken))
    qualities = [t.review_quality for t in completed if t.review_quality is not None]
    avg_quality = round(sum(qualities) / len(qualities)) if qualities else 0
    accuracy_score = round(avg_quality / 20, 1)  # 0–100 → 0–5

    on_time = 0
    submitted = [t for t in tasks if t.submitted_at is not None and t.accepted_at is not None]
    for t in submitted:
        hours = (t.submitted_at - t.accepted_at).total_seconds() / 3600
        if hours <= task_sla_hours:
            on_time += 1
    timeliness_rate = _pct(on_time, len(submitted))

    decline_count = sum((t.decline_count or 0) for t in tasks)
    penalty = min(decline_count * _DECLINE_PENALTY_PER, _MAX_DECLINE_PENALTY)
    raw = (
        _W_COMPLETION * completion_rate
        + _W_ACCURACY * (accuracy_score / 5 * 100)
        + _W_TIMELINESS * timeliness_rate
    )
    composite = max(0, min(100, round(raw) - penalty))

    active_since = min(
        (t.accepted_at or t.date_created for t in tasks if (t.accepted_at or t.date_created)),
        default=None,
    )
    return AgentMetrics(
        total_jobs=total, completed_jobs=len(completed), completion_rate=completion_rate,
        avg_quality=avg_quality, accuracy_score=accuracy_score, timeliness_rate=timeliness_rate,
        decline_count=decline_count, composite_score=composite, active_since=active_since,
    )


def _pct(numerator: int, denominator: int) -> int:
    return round(numerator / denominator * 100) if denominator else 0

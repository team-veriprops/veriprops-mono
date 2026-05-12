"""Unit tests for agent metrics computation (S49)."""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from main.app.domain.user.agent.models import AgentMetricsDto, AvailabilityStatus
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


def _make_metrics(
    completion_rate: float = 0.0,
    accuracy_score: float = 0.0,
    timeliness_score: float = 0.0,
    total_jobs: int = 0,
    active_since: datetime | None = None,
) -> AgentMetricsDto:
    return AgentMetricsDto(
        completion_rate=completion_rate,
        accuracy_score=accuracy_score,
        timeliness_score=timeliness_score,
        total_jobs=total_jobs,
        active_since=active_since,
    )


class TestMetricsDto:
    def test_zero_jobs_all_zeros(self):
        m = _make_metrics(total_jobs=0)
        assert m.completion_rate == 0.0
        assert m.accuracy_score == 0.0
        assert m.timeliness_score == 0.0
        assert m.total_jobs == 0

    def test_full_completion_rate(self):
        m = _make_metrics(completion_rate=100.0, total_jobs=10)
        assert m.completion_rate == 100.0

    def test_partial_completion_rate(self):
        # 6 approved out of 10 total accepted = 60%
        m = _make_metrics(completion_rate=60.0, total_jobs=10)
        assert m.completion_rate == 60.0

    def test_accuracy_score_range(self):
        m = _make_metrics(accuracy_score=4.5, total_jobs=5)
        assert 0.0 <= m.accuracy_score <= 5.0

    def test_timeliness_score_range(self):
        m = _make_metrics(timeliness_score=85.0, total_jobs=8)
        assert 0.0 <= m.timeliness_score <= 100.0

    def test_active_since_preserved(self):
        ts = datetime(2024, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
        m = _make_metrics(active_since=ts)
        assert m.active_since == ts


class TestCompositeScoreFormula:
    """Verify the composite ranking formula: 0.4*accuracy/5 + 0.4*completion/100 + 0.2*timeliness/100."""

    def _composite(self, accuracy: float, completion: float, timeliness: float) -> float:
        return 0.4 * (accuracy / 5.0) + 0.4 * (completion / 100.0) + 0.2 * (timeliness / 100.0)

    def test_perfect_agent_scores_1(self):
        score = self._composite(5.0, 100.0, 100.0)
        assert abs(score - 1.0) < 1e-9

    def test_zero_agent_scores_0(self):
        score = self._composite(0.0, 0.0, 0.0)
        assert score == 0.0

    def test_partial_scores(self):
        score = self._composite(4.0, 80.0, 75.0)
        expected = 0.4 * (4.0 / 5.0) + 0.4 * (80.0 / 100.0) + 0.2 * (75.0 / 100.0)
        assert abs(score - expected) < 1e-9

    def test_accuracy_and_completion_weighted_equally(self):
        # Both components carry 0.4 weight — adjusting by same delta changes score equally
        s_high_accuracy = self._composite(5.0, 40.0, 50.0)
        s_high_completion = self._composite(3.0, 80.0, 50.0)
        # accuracy delta: +2.0/5.0 * 0.4 = +0.16; completion delta: +40/100 * 0.4 = +0.16
        assert abs(s_high_accuracy - s_high_completion) < 1e-9

    def test_ordering_top_agent_threshold(self):
        # Top agent requires accuracy >= 4.5 and completion >= 80
        top_score = self._composite(4.5, 80.0, 70.0)
        regular_score = self._composite(4.4, 79.0, 70.0)
        assert top_score > regular_score


class TestAvailabilityStatus:
    def test_values(self):
        assert AvailabilityStatus.AVAILABLE.value == "AVAILABLE"
        assert AvailabilityStatus.LIMITED.value == "LIMITED"
        assert AvailabilityStatus.UNAVAILABLE.value == "UNAVAILABLE"

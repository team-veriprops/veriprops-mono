"""Pure agent reputation metrics (§16.1, D32)."""
from datetime import timedelta
from types import SimpleNamespace

from main.app.core.state.status import TaskState
from main.app.domain.user.agent.reputation.metrics import compute_metrics
from main.appodus_utils import Utils

NOW = Utils.datetime_now()


def _task(state=TaskState.APPROVED, quality=100, declines=0, accepted_ago_h=None, submit_after_h=None):
    accepted = NOW - timedelta(hours=accepted_ago_h) if accepted_ago_h is not None else None
    submitted = (accepted + timedelta(hours=submit_after_h)) if (accepted and submit_after_h is not None) else None
    return SimpleNamespace(
        state=state.value, review_quality=quality, decline_count=declines,
        accepted_at=accepted, submitted_at=submitted, date_created=NOW,
    )


class TestCompletion:
    def test_completion_rate_is_approved_over_taken(self):
        tasks = [
            _task(TaskState.APPROVED, accepted_ago_h=10),
            _task(TaskState.APPROVED, accepted_ago_h=10),
            _task(TaskState.IN_PROGRESS, accepted_ago_h=10),
            _task(TaskState.REJECTED, accepted_ago_h=10),
        ]
        m = compute_metrics(tasks, task_sla_hours=48)
        assert m.completion_rate == 50  # 2 approved of 4 taken
        assert m.total_jobs == 4
        assert m.completed_jobs == 2


class TestAccuracy:
    def test_accuracy_is_avg_quality_on_five_point_scale(self):
        tasks = [_task(quality=80, accepted_ago_h=1), _task(quality=100, accepted_ago_h=1)]
        m = compute_metrics(tasks, task_sla_hours=48)
        assert m.avg_quality == 90
        assert m.accuracy_score == 4.5  # 90 / 20

    def test_no_completed_jobs_zero_accuracy(self):
        m = compute_metrics([_task(TaskState.IN_PROGRESS, accepted_ago_h=1)], task_sla_hours=48)
        assert m.accuracy_score == 0
        assert m.avg_quality == 0


class TestTimeliness:
    def test_within_sla_counts_as_on_time(self):
        tasks = [
            _task(accepted_ago_h=50, submit_after_h=10),   # 10h ≤ 48 on time
            _task(accepted_ago_h=100, submit_after_h=72),  # 72h > 48 late
        ]
        m = compute_metrics(tasks, task_sla_hours=48)
        assert m.timeliness_rate == 50


class TestCompositeAndDeclines:
    def test_declines_penalise_composite(self):
        clean = compute_metrics([_task(quality=100, accepted_ago_h=50, submit_after_h=1)], 48)
        penalised = compute_metrics([_task(quality=100, declines=2, accepted_ago_h=50, submit_after_h=1)], 48)
        assert penalised.composite_score < clean.composite_score
        assert penalised.decline_count == 2

    def test_perfect_agent_scores_100(self):
        m = compute_metrics([_task(quality=100, accepted_ago_h=50, submit_after_h=1)], 48)
        assert m.composite_score == 100

    def test_composite_never_negative(self):
        tasks = [_task(TaskState.REJECTED, quality=0, declines=20, accepted_ago_h=1)]
        m = compute_metrics(tasks, 48)
        assert m.composite_score >= 0

    def test_active_since_is_earliest(self):
        old = _task(accepted_ago_h=100)
        new = _task(accepted_ago_h=1)
        m = compute_metrics([new, old], 48)
        assert m.active_since == old.accepted_at

    def test_empty_history(self):
        m = compute_metrics([], 48)
        assert m.total_jobs == 0 and m.composite_score == 0 and m.active_since is None

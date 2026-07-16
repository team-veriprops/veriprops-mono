"""Scheduler wiring (app/jobs/scheduled.py): every sweep entrypoint is registered
with its expected cadence, and the scheduler never starts under the test
environment (automation-determinism contract — sweeps run directly in tests)."""
from datetime import timedelta
from types import SimpleNamespace

from main.app.jobs import scheduled
from main.appodus_utils.config.settings import Environment

# id -> interval minutes; cadences are part of the ops contract (see the
# registration comments in scheduled.py for why each runs at its rate).
EXPECTED_JOBS = {
    "pool_timeout_check": 15,
    "no_show_check": 15,
    "sla_breach_check": 30,
    "commission_clearance_check": 60,
    "abandonment_recovery_check": 60,
    "referral_credit_check": 180,
    "scheduled_broadcast_check": 5,
    "message_retry_check": 1,
}


def test_all_sweeps_registered_with_expected_intervals():
    jobs = {job.id: job for job in scheduled.scheduler.get_jobs()}
    assert set(jobs) == set(EXPECTED_JOBS)
    for job_id, minutes in EXPECTED_JOBS.items():
        assert jobs[job_id].trigger.interval == timedelta(minutes=minutes), job_id


def test_start_scheduler_is_noop_under_test_environment(monkeypatch):
    # The suite itself runs with ENVIRONMENT=dev_personal (no .env.test exists), so pin
    # the module's settings view to TEST to exercise the determinism guard.
    monkeypatch.setattr(
        scheduled, "settings", SimpleNamespace(ENVIRONMENT=Environment.TEST)
    )
    scheduled.start_scheduler()
    assert not scheduled.scheduler.running

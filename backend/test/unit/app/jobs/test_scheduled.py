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
    "assistant_pending_turn_check": 1,
    "expired_key_value_cleanup": 60,
    "unprocessed_whatsapp_inbound_check": 5,
}
# id -> (hour, minute) in Africa/Lagos, for the jobs that run at a time of day.
EXPECTED_DAILY_JOBS = {
    # Approved payouts leave once a day, while banks are settling (§15.1).
    "payout_disbursement": (10, 0),
}


def test_all_sweeps_registered_with_expected_intervals():
    jobs = {job.id: job for job in scheduled.scheduler.get_jobs()}
    assert set(jobs) == set(EXPECTED_JOBS) | set(EXPECTED_DAILY_JOBS)
    for job_id, minutes in EXPECTED_JOBS.items():
        assert jobs[job_id].trigger.interval == timedelta(minutes=minutes), job_id


def test_daily_jobs_run_at_their_lagos_time():
    jobs = {job.id: job for job in scheduled.scheduler.get_jobs()}
    for job_id, (hour, minute) in EXPECTED_DAILY_JOBS.items():
        trigger = jobs[job_id].trigger
        fields = {f.name: str(f) for f in trigger.fields}
        assert (fields["hour"], fields["minute"]) == (str(hour), str(minute)), job_id
        assert str(trigger.timezone) == "Africa/Lagos", job_id


def test_start_scheduler_is_noop_under_test_environment(monkeypatch):
    # The suite itself runs with ENVIRONMENT=dev_personal (no .env.test exists), so pin
    # the module's settings view to TEST to exercise the determinism guard.
    monkeypatch.setattr(
        scheduled, "settings", SimpleNamespace(ENVIRONMENT=Environment.TEST)
    )
    scheduled.start_scheduler()
    assert not scheduled.scheduler.running

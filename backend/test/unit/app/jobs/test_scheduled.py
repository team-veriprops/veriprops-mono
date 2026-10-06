"""Job registry and scheduler wiring (app/jobs/registry.py, app/jobs/scheduled.py).

Every sweep is declared once in `JOB_REGISTRY` with its cadence. Two clocks run the same
tick over it: the Cloudflare Cron Worker on the deployed (serverless) environments, and the
in-process scheduler on local and long-running hosts — so the scheduler holds exactly one
job, the tick, and never starts under the test environment (automation-determinism
contract: sweeps run directly in tests)."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from main.app.jobs import scheduled
from main.app.jobs.registry import JOB_REGISTRY, job_named
from main.appodus_utils.config.settings import Environment

# name -> interval minutes; cadences are part of the ops contract (see the
# registration comments in registry.py for why each runs at its rate).
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
# name -> (hour, minute) in Africa/Lagos, for the jobs that run at a time of day.
EXPECTED_DAILY_JOBS = {
    # Approved payouts leave once a day, while banks are settling (§15.1).
    "payout_disbursement": (10, 0),
}
_LAGOS = ZoneInfo("Africa/Lagos")


def test_every_sweep_is_registered_once():
    names = [job.name for job in JOB_REGISTRY]
    assert len(names) == len(set(names))
    assert set(names) == set(EXPECTED_JOBS) | set(EXPECTED_DAILY_JOBS)


def test_interval_jobs_fire_one_interval_after_their_anchor():
    anchor = datetime(2026, 10, 6, 12, 0, 7, tzinfo=timezone.utc)
    for name, minutes in EXPECTED_JOBS.items():
        assert job_named(name).next_fire_after(anchor) == anchor + timedelta(minutes=minutes), name


def test_daily_jobs_fire_at_their_next_lagos_time():
    for name, (hour, minute) in EXPECTED_DAILY_JOBS.items():
        job = job_named(name)
        before = datetime(2026, 10, 6, hour, minute, tzinfo=_LAGOS) - timedelta(hours=1)
        assert job.next_fire_after(before) == datetime(2026, 10, 6, hour, minute, tzinfo=_LAGOS), name
        # A run at the fire time itself waits for the next day, never repeats.
        at = datetime(2026, 10, 6, hour, minute, tzinfo=_LAGOS)
        assert job.next_fire_after(at) == datetime(2026, 10, 7, hour, minute, tzinfo=_LAGOS), name


def test_the_scheduler_holds_only_the_minutely_tick():
    jobs = scheduled.scheduler.get_jobs()
    assert [job.id for job in jobs] == [scheduled.TICK_JOB_ID]
    assert jobs[0].trigger.interval == timedelta(minutes=1)


def test_start_scheduler_is_noop_under_test_environment(monkeypatch):
    # The suite itself runs with ENVIRONMENT=dev_personal (no .env.test exists), so pin
    # the module's settings view to TEST to exercise the determinism guard.
    monkeypatch.setattr(
        scheduled, "settings", SimpleNamespace(ENVIRONMENT=Environment.TEST)
    )
    scheduled.start_scheduler()
    assert not scheduled.scheduler.running

"""Stage 16 (last) — outbound-message failure → retry → threshold → expiry pipeline.

Induces a REAL SMTP failure by stopping the Mailpit container (docker CLI, name from
``MAILPIT_CONTAINER``, default ``veriprops-mono-mailpit-1``), then drives the retry
pipeline through the admin sweep endpoint. Determinism against the default
``[60, 300, 900]`` backoff ladder comes from ``POST /dev/messages/rewind``, which pulls
``next_retry_at``/``expires_at`` into the past so each sweep fires immediately.

Degrades cleanly (run stays green): warn-skips when Mailpit is unreachable, the docker
CLI can't stop the container, or the backend runs ``ENABLE_OUT_MESSAGING=False`` (no
bookkeeping row ever appears). Mailpit is ALWAYS restarted, even when a check fails.
Runs after ``email`` because it takes SMTP down mid-stage.
"""
from __future__ import annotations

import os
import subprocess
import time
import uuid

import httpx

from .harness import Ctx, check, warn

MAILPIT = "http://localhost:8025"
MAILPIT_CONTAINER = os.environ.get("MAILPIT_CONTAINER", "veriprops-mono-mailpit-1")


def _docker(*args: str) -> bool:
    try:
        return subprocess.run(["docker", *args], capture_output=True, text=True,
                              timeout=60).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _mailpit_reachable() -> bool:
    try:
        httpx.get(f"{MAILPIT}/api/v1/messages", params={"limit": 1}, timeout=5).raise_for_status()
        return True
    except httpx.HTTPError:
        return False


def _mailpit_count(query: str) -> int:
    try:
        r = httpx.get(f"{MAILPIT}/api/v1/search", params={"query": query}, timeout=10)
        return len(r.json().get("messages") or [])
    except httpx.HTTPError:
        return -1


def _row(ctx: Ctx, recipient: str) -> dict:
    """Latest bookkeeping row for *recipient* via the dev determinism endpoint."""
    return ctx.root.get("/dev/messages/latest",
                        params={"recipient": recipient}).json()["data"]


def _rewind(ctx: Ctx, recipient: str, *, expiry: bool = False) -> None:
    ctx.root.post("/dev/messages/rewind",
                  params={"recipient": recipient, "rewind_expiry": expiry}).raise_for_status()


def _sweep(ctx: Ctx) -> dict:
    r = ctx.admin.post("/messages/sweeps/retries")
    check("admin retry sweep responds (POST /messages/sweeps/retries)",
          r.status_code == 200, f"http {r.status_code}")
    return r.json().get("data", {}) if r.status_code == 200 else {}


def run(ctx: Ctx) -> None:
    if not _mailpit_reachable():
        warn("Mailpit not reachable on :8025 — messaging-retry assertions skipped",
             "run `docker compose up -d mailpit` + ENABLE_OUT_MESSAGING=True to cover retries")
        return
    if not _docker("stop", MAILPIT_CONTAINER):
        warn("docker CLI could not stop the Mailpit container — messaging-retry skipped",
             f"container '{MAILPIT_CONTAINER}' (override via MAILPIT_CONTAINER)")
        return

    reset_email = ctx.seed["customer"]["email"]
    otp_email = f"qa-retryqa-{uuid.uuid4().hex[:8]}@veriprops.io"
    reset_inbox_before = 0  # counted after Mailpit is back up

    try:
        # 1. Initial failures are stored and scheduled for retry (§12 bookkeeping).
        ctx.root.post("/users/auth/password/forgot", json={"email": reset_email}).raise_for_status()
        r = ctx.root.post("/users/auth/otp/send",
                          json={"channel": "EMAIL", "email": otp_email, "fullname": "Retry QA"})
        check("otp send accepted while SMTP is down", r.status_code == 200, f"http {r.status_code}")
        time.sleep(1)

        reset_row = _row(ctx, reset_email)
        if not reset_row.get("found"):
            warn("no message bookkeeping row — backend likely runs ENABLE_OUT_MESSAGING=False",
                 "restart it with ENABLE_OUT_MESSAGING=True to cover the retry pipeline")
            return
        check("failed send is stored RETRYING with retry_count=0 and a next_retry_at",
              reset_row["status"] == "retrying" and reset_row["retry_count"] == 0
              and reset_row["next_retry_at_set"], str(reset_row))
        otp_row = _row(ctx, otp_email)
        check("OTP row carries its expires_at horizon (time-bound content)",
              otp_row.get("found") and otp_row["status"] == "retrying"
              and otp_row["expires_at_set"], str(otp_row))

        # 2. Ladder climbs to the threshold (len(intervals) retries), then permanent FAILED.
        for expected_rc in (1, 2):
            _rewind(ctx, reset_email)
            _sweep(ctx)
            reset_row = _row(ctx, reset_email)
            check(f"failed retry #{expected_rc} reschedules with retry_count={expected_rc}",
                  reset_row["status"] == "retrying" and reset_row["retry_count"] == expected_rc,
                  str(reset_row))
        _rewind(ctx, reset_email)
        stats = _sweep(ctx)
        reset_row = _row(ctx, reset_email)
        check("final failed retry exhausts the threshold → permanent FAILED",
              reset_row["status"] == "failed", f"{reset_row} sweep={stats}")
        _rewind(ctx, reset_email)
        stats = _sweep(ctx)
        check("a permanently FAILED message is never re-dispatched",
              not stats.get("processed") and not stats.get("retried"), str(stats))

        # 3. Expired time-bound content permanently fails WITHOUT dispatch (stale OTP).
        _rewind(ctx, otp_email, expiry=True)
        stats = _sweep(ctx)
        otp_row = _row(ctx, otp_email)
        check("expired OTP row fails permanently without re-dispatch",
              otp_row["status"] == "failed" and stats.get("expired", 0) >= 1,
              f"{otp_row} sweep={stats}")
        check("expiry failure records an 'expired' error", "xpire" in (otp_row.get("error") or ""),
              str(otp_row.get("error"))[:80])

        # 4. Recovery: a queued failure delivers once SMTP is back.
        ctx.root.post("/users/auth/password/forgot", json={"email": reset_email}).raise_for_status()
        time.sleep(1)
        reset_row = _row(ctx, reset_email)
        check("second reset mail queued RETRYING while SMTP still down",
              reset_row["status"] == "retrying" and reset_row["retry_count"] == 0, str(reset_row))
    finally:
        _docker("start", MAILPIT_CONTAINER)
        for _ in range(30):
            if _mailpit_reachable():
                break
            time.sleep(1)

    if not _mailpit_reachable():
        warn("Mailpit did not come back up — recovery assertions skipped")
        return

    reset_inbox_before = _mailpit_count(f'to:"{reset_email}" subject:"reset"')
    _rewind(ctx, reset_email)
    stats = _sweep(ctx)
    reset_row = _row(ctx, reset_email)
    check("sweep delivers the queued row after SMTP recovery (→ SENT)",
          reset_row["status"] == "sent" and stats.get("processed", 0) >= 1,
          f"{reset_row} sweep={stats}")
    check("recovered reset email actually landed in Mailpit",
          _mailpit_count(f'to:"{reset_email}" subject:"reset"') > reset_inbox_before)

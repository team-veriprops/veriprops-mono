"""Live cradle-to-grave end-to-end drive-through of the whole PRD spine (S1–S23).

Runs against a real backend on :8000. One continuous scenario: the session-refresh
auth contract (silent re-auth happy path + CSRF/missing-cookie/revoked failures) → a fresh customer signs up
(email OTP + consents + the seeded customer's referral code) → agent onboarding/KYC + admin
invitation RBAC → draft/quote/submit → stub payment → assignment → agent execution with
content-hashed evidence → chat + fraud hold/reject + SLA sweep → admin review (reject/rework
cycle, release gate) → release → report + branded PDF → tracking/SSE → public sharing →
dispute/re-check/upgrade → payouts → the finished PREMIUM leg (LAWYER + v2/v3 reports,
declined re-check, upheld dispute) → referral earn+spend → pricing/analytics/broadcast
hardening → pool/no-show/starvation + pause/delay/cancel/fail + chargeback → audit pack +
NDPA erasure (reject + execute) → the WhatsApp channel (signature-verified Meta webhook,
redelivery dedup, console inbound under the same fraud scan, and a handoff link carried all
the way to a PAID case) → Mailpit email delivery + password reset → outbound-message
failure→retry→threshold→expiry pipeline (stops/starts the Mailpit container via the docker
CLI; warn-skips without docker). Prints PASS/FAIL per step; exits non-zero on any failure.

Stages live in scripts/e2e/ (shared harness in scripts/e2e/harness.py). Stages have linear
data dependencies (each builds on the previous), so ``--stages`` subsets must be contiguous
prefixes of the default order.

How to run (non-prod only — uses /dev/reset + /dev/seed):
    # 1. migrate the local DB (base→head recreates the current 0001 schema):
    set APPODUS_ACTIVE_ENV=dev_personal && alembic downgrade base && alembic upgrade head
    # 2. Mailpit captures real SMTP so the email stage can assert delivery:
    docker compose up -d mailpit
    # 3. start the backend with outbound messaging ON (email → Mailpit, SMS → mock):
    set APPODUS_ACTIVE_ENV=dev_personal && set ENABLE_OUT_MESSAGING=True && python veriprops.py
    # 4. run the full drive-through (or a prefix, e.g. --stages session_refresh,onboarding):
    set PYTHONIOENCODING=utf-8 && python scripts/e2e_drive_through.py

Without Mailpit (or with ENABLE_OUT_MESSAGING=False) everything still passes — the final
email + messaging_retry stages detect the situation and warn-skip instead of failing. The
messaging_retry stage additionally needs the docker CLI (it stops/starts the Mailpit
container to induce a real SMTP failure; override the name via MAILPIT_CONTAINER).
"""
from __future__ import annotations

import argparse
import sys

from e2e import (
    stage_admin_ops,
    stage_admin_team,
    stage_aftermarket,
    stage_agent_onboarding,
    stage_comms,
    stage_compliance,
    stage_email,
    stage_execution,
    stage_growth,
    stage_messaging_retry,
    stage_onboarding,
    stage_ops_unhappy,
    stage_premium_release,
    stage_review_release,
    stage_session_refresh,
    stage_sharing,
    stage_tracking,
    stage_whatsapp,
)
from e2e.harness import Ctx, check, checks_run, client, failures, login

# Ordered pipeline — each stage consumes state the previous ones produced (Ctx).
STAGES = [
    ("session_refresh", stage_session_refresh),      # §2 — FetchHttpClient silent re-auth contract
    ("onboarding", stage_onboarding),                # Phases 2+5, §17.1 quote/re-lock
    ("agent_onboarding", stage_agent_onboarding),    # S7 — application, KYC stub, approve/reject
    ("admin_team", stage_admin_team),                # S8 — invite, accept, RBAC, revoke, deactivate
    ("execution", stage_execution),                  # S10/S11 — assign → evidence → submit
    ("comms", stage_comms),                          # S15/S16 — chat, fraud hold+reject, SLA sweep
    ("review_release", stage_review_release),        # S12/S14 — review cycle, release, PDF
    ("tracking", stage_tracking),                    # S13 — tracking, activity, SSE
    ("sharing", stage_sharing),                      # S17 — public lookup + shares
    ("aftermarket", stage_aftermarket),              # S18/S19/S20 — disputes, payouts, reputation
    ("premium_release", stage_premium_release),      # §14 finish — LAWYER, v2/v3, declined recheck
    ("growth", stage_growth),                        # S21 — referral earn + spend, abandonment
    ("admin_ops", stage_admin_ops),                  # S22 — pricing, analytics, broadcast hardening
    ("ops_unhappy", stage_ops_unhappy),              # §6/§7.2/§8.5/§6a — pool, lifecycle, chargeback
    ("compliance", stage_compliance),                # S23 — audit pack, erasure reject + execute
    ("whatsapp", stage_whatsapp),                    # §7 S1–S3 — signed webhook, console inbound, handoff
    ("email", stage_email),                          # Mailpit delivery + password reset (warn-skips)
    ("messaging_retry", stage_messaging_retry),      # failure→retry→threshold→expiry (warn-skips)
]


def _prologue() -> Ctx:
    """Reset + seed a deterministic scenario, then zero the clearance windows up front.

    ``chargeback_window_days`` must be zeroed BEFORE the fresh customer's first payment:
    the referral credit's ``clearing_until`` is computed from it at credit-creation time
    (§17.1, D35), so a later edit would leave the credit unclearable within the run. The
    commission windows likewise let the release-accrued commissions clear in-run (§15.2).
    """
    root = client()
    root.post("/dev/reset").raise_for_status()
    seed = root.post("/dev/seed").json()["data"]
    check("dev seed created an UNDER_REVIEW verification",
          seed["verification"]["status"] == "UNDER_REVIEW")

    admin = login(seed["admin"]["email"], seed["admin"]["password"])
    for key in ("commission_clearance_days", "commission_reserve_pct", "chargeback_window_days"):
        admin.put(f"/admin/config/settings/{key}", json={"value": 0}).raise_for_status()

    seed_customer = login(seed["customer"]["email"], seed["customer"]["password"])
    return Ctx(root=root, admin=admin, seed=seed, seed_customer=seed_customer)


def main() -> int:
    names = [n for n, _ in STAGES]
    parser = argparse.ArgumentParser(
        description="Live cradle-to-grave e2e drive-through (non-prod only).")
    parser.add_argument(
        "--stages",
        help="Comma-separated contiguous prefix of the stage order to run "
             f"(default: all). Order: {','.join(names)}",
    )
    args = parser.parse_args()

    selected = names
    if args.stages:
        wanted = [s.strip() for s in args.stages.split(",") if s.strip()]
        unknown = [s for s in wanted if s not in names]
        if unknown:
            parser.error(f"unknown stage(s): {unknown}; valid: {names}")
        if wanted != names[: len(wanted)]:
            parser.error(
                "stages have linear data dependencies — pass a contiguous prefix "
                f"of: {','.join(names)}"
            )
        selected = wanted

    ctx = _prologue()
    for name, module in STAGES:
        if name not in selected:
            break
        print(f"\n── stage: {name} " + "─" * max(0, 58 - len(name)))
        module.run(ctx)

    failed = failures()
    # The total is counted rather than left to be grepped out of the [PASS] lines, which
    # is how the figures quoted in docs/runtime-state.yaml used to be arrived at.
    summary = f"{checks_run()} checks"
    if failed:
        summary += f", {len(failed)} FAILED: {failed}"
    print("\n" + ("ALL PASSED — " if not failed else "") + summary)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

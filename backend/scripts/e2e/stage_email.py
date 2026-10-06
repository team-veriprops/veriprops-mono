"""Stage 15 (last) — real email delivery via Mailpit + the password-reset flow (§2, §12.2).

Requires the backend to run with ENABLE_OUT_MESSAGING=True and Mailpit on localhost:1025/8025
(`docker compose up -d mailpit`). Off CI it degrades cleanly: if Mailpit is unreachable or
captured nothing, the stage warns and returns; in CI (`CI=true`) that is a failure, because the
stack is provisioned there and a skip would hide a broken delivery path. Runs LAST because the
password reset revokes the fresh customer's sessions (ctx.customer becomes unusable).
"""
from __future__ import annotations

import re

from .harness import QA_PASSWORD, Ctx, check, login_status, skip_unless_ci
from .mailpit import mailpit_total, message_text, search_mail as _search


def run(ctx: Ctx) -> None:
    total = mailpit_total()
    if total is None:
        skip_unless_ci("Mailpit not reachable on :8025 — email assertions skipped",
             "run `docker compose up -d mailpit` + ENABLE_OUT_MESSAGING=True to cover email")
        return
    if total == 0:
        skip_unless_ci("Mailpit captured no mail — backend likely runs ENABLE_OUT_MESSAGING=False",
             "restart it with ENABLE_OUT_MESSAGING=True to cover email delivery")
        return

    email = ctx.customer_email

    # 1. Transactional emails actually landed over SMTP (§12.2 external fan-out).
    check("signup OTP email delivered over SMTP (§2)",
          len(_search(f'to:"{email}" subject:"code"')) > 0
          or len(_search(f'to:"{email}"')) > 0, f"inbox for {email}")
    check("REPORT_READY email delivered to the customer (§12.2)",
          len(_search(f'to:"{email}" subject:"report"')) > 0)
    check("broadcast announcement email delivered (§18.1, D37)",
          len(_search('subject:"Maintenance window"')) > 0)
    # The share invite is best-effort, so a broken send leaves share creation green — only
    # the recipient's inbox shows whether it went. Scoped to this run's VID, because Mailpit
    # keeps mail across runs and an earlier run's invite would otherwise satisfy the check.
    check("named report-share invite delivered to the recipient (§13.2)",
          len(_search(f'to:"friend@example.com" {ctx.vid}')) > 0)

    # 2. Password reset — the token only ever surfaces in the email (§2).
    ctx.root.post("/users/auth/password/forgot", json={"email": email}).raise_for_status()
    reset_msgs = _search(f'to:"{email}" subject:"reset"') or _search(f'to:"{email}"')
    check("password-reset email delivered (§2)", len(reset_msgs) > 0)
    token = ""
    if reset_msgs:
        text = message_text(reset_msgs[0]['ID'])
        m = re.search(r"/auth/reset-password/([A-Za-z0-9]+)", text)
        token = m.group(1) if m else ""
    check("reset email carries the tokenised reset link (§2)", bool(token))
    if not token:
        return

    new_password = "NewTest5678!"
    r = ctx.root.post("/users/auth/password/reset", json={"token": token, "password": new_password})
    check("password reset consumes the token (§2)", r.status_code == 200, f"http {r.status_code}")
    check("old password no longer logs in (§2)", login_status(email, QA_PASSWORD) != 200)
    check("new password logs in (§2)", login_status(email, new_password) == 200)
    stale = ctx.customer.post("/users/auth/sessions/current")
    check("reset revoked the pre-reset session (refresh rejected, §2.4)",
          stale.status_code >= 400, f"http {stale.status_code}")

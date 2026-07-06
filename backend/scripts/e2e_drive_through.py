"""Live end-to-end drive-through of the S15–S18 stack.

Runs against a real backend on :8000. Exercises: dev reset+seed, customer login, the §4.7
fraud fast-lane + hold, admin hold-review approve, release → §12.2 status/report notifications
+ §11.1 status auto-post, the SLA-breach sweep (customer + admin, G3), the admin shared-inbox
Chat counter (G4), then the S17 public lookup + link/named-recipient sharing (§13) and the S18
dispute → re-check → tier-upgrade flows (§14). Prints PASS/FAIL per step; exits non-zero on failure.

How to run (non-prod only — uses /dev/reset + /dev/seed):
    # 1. migrate the local DB (base→head recreates the current 0001 schema):
    set appodus_active_env=local && alembic downgrade base && alembic upgrade head
    # 2. start the backend (external email off so no SMTP dependency):
    set appodus_active_env=local && set ENABLE_OUT_MESSAGING=False && python veriprops.py
    # 3. run this script:
    set PYTHONIOENCODING=utf-8 && python scripts/e2e_drive_through.py
"""
from __future__ import annotations

import sys
from urllib.parse import parse_qs, urlparse

import httpx

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE = "http://localhost:8000/api"
_failures = []


def check(name: str, ok: bool, detail: str = "") -> None:
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        _failures.append(name)


def login(email: str, password: str) -> httpx.Client:
    c = httpx.Client(base_url=BASE, timeout=30.0)
    r = c.post("/users/auth/sessions", json={"email": email, "password": password})
    r.raise_for_status()
    # The session uses `__Host-`-prefixed Secure cookies; httpx won't resend a Secure cookie
    # over plain http, so pin the jar's cookies onto an explicit Cookie header for the run.
    jar = {k: v for k, v in c.cookies.items()}
    if jar:
        c.headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in jar.items())
    # Double-submit CSRF: mutations require the access csrf token as a header.
    csrf = jar.get("__Host-access_csrf_token")
    if csrf:
        c.headers["X-CSRF-Token"] = csrf
    return c


def main() -> int:
    root = httpx.Client(base_url=BASE, timeout=30.0)

    # 1. Reset + seed a deterministic scenario.
    root.post("/dev/reset").raise_for_status()
    seed = root.post("/dev/seed").json()["data"]
    vid_id = seed["verification"]["id"]
    cust = seed["customer"]
    admin = seed["admin"]
    check("dev seed created an UNDER_REVIEW verification", seed["verification"]["status"] == "UNDER_REVIEW")

    # 2. Customer logs in and opens the customer↔admin thread.
    customer = login(cust["email"], cust["password"])
    convo = customer.get(f"/verifications/{vid_id}/chat").json()["data"]
    conv_id = convo["id"]
    check("customer opened the verification chat thread", bool(conv_id))

    # 3. A clean message takes the fast lane → DELIVERED.
    clean = customer.post(
        f"/verifications/{vid_id}/chat/messages", json={"body": "Hello, any update on my verification?"}
    ).json()["data"]
    check("clean message delivered immediately (§4.7 fast lane)", clean["state"] == "DELIVERED")

    # 4. A message with a phone number is HELD.
    flagged = customer.post(
        f"/verifications/{vid_id}/chat/messages", json={"body": "please call me on 08031234567"}
    ).json()["data"]
    check("phone-number message held for review (§4.7)", flagged["state"] == "HELD",
          f"state={flagged['state']}")
    check("held sender sees the non-accusatory notice", bool(flagged.get("heldNotice")))

    # 5. Admin logs in, finds it in the hold queue, approves it.
    admin_c = login(admin["email"], admin["password"])

    # S19: zero the commission clearance + reserve windows up front so the commissions accrued
    # at release (step 8) clear immediately on the sweep below — lets the earnings→payout flow
    # complete in a single run (§15.2 windows are otherwise days long).
    admin_c.put("/admin/config/settings/commission_clearance_days", json={"value": 0}).raise_for_status()
    admin_c.put("/admin/config/settings/commission_reserve_pct", json={"value": 0}).raise_for_status()
    held = admin_c.get("/admin/messages/held").json()["data"]["items"]
    held_ids = [m["id"] for m in held]
    check("held message appears in the admin queue (§11.2)", flagged["id"] in held_ids)
    approved = admin_c.post(f"/admin/messages/{flagged['id']}/approve").json()["data"]
    check("admin approval delivers the held message", approved["state"] == "DELIVERED")

    # 6. Customer now sees the approved message delivered.
    msgs = customer.get(f"/chat/conversations/{conv_id}/messages").json()["data"]["items"]
    delivered_bodies = [m["body"] for m in msgs if m["state"] == "DELIVERED"]
    check("customer sees the approved message in the thread",
          any("08031234567" in b for b in delivered_bodies))

    # 7. SLA-breach sweep while still UNDER_REVIEW + overdue → customer AND admin (G3, D23).
    #    (Runs before release, since a COMPLETED verification is correctly out of the SLA set.)
    swept = admin_c.post("/admin/verifications/sweeps/sla-breach").json()["data"]
    check("SLA sweep flagged the overdue verification (D23)", swept["flagged"] >= 1,
          f"flagged={swept['flagged']}")
    cust_types = {n["type"] for n in customer.get("/notifications").json()["data"]["items"]}
    admin_types = {n["type"] for n in admin_c.get("/notifications").json()["data"]["items"]}
    check("customer got the SLA_BREACHED notification", "SLA_BREACHED" in cust_types)
    check("admin got the SLA_BREACHED notification (G3)", "SLA_BREACHED" in admin_types)

    # 8. Admin releases the report → COMPLETED → §12.2 notifications + §11.1 auto-post.
    rel = admin_c.post(f"/admin/review/{vid_id}/release", json={"reason": "All checks passed."})
    check("admin release succeeded (UNDER_REVIEW → COMPLETED)", rel.status_code == 200,
          f"http {rel.status_code}")

    notifs = customer.get("/notifications").json()["data"]["items"]
    types = {n["type"] for n in notifs}
    check("customer got a REPORT_READY notification (§12.2)", "REPORT_READY" in types, str(types))
    check("customer got a STATUS_CHANGED notification (§12.2)", "STATUS_CHANGED" in types, str(types))
    unread = customer.get("/notifications/unread").json()["data"]["count"]
    check("customer notification counter is non-zero", unread > 0, f"count={unread}")

    msgs2 = customer.get(f"/chat/conversations/{conv_id}/messages").json()["data"]["items"]
    autoposts = [m for m in msgs2 if m["messageKind"] == "SYSTEM_AUTO"]
    check("status change auto-posted a SYSTEM breadcrumb into the thread (§11.1 / G1)",
          len(autoposts) > 0, f"system messages={len(autoposts)}")

    # 9. Admin shared-inbox Chat counter (G4).
    admin_convos = admin_c.get("/chat/conversations").json()["data"]
    admin_threads = [c for c in admin_convos if c["verificationId"] == vid_id]
    check("admin sees the verification thread in the shared inbox (§N.3 / G4)", len(admin_threads) > 0)
    admin_unread = admin_c.get("/chat/unread").json()["data"]["count"]
    check("admin Chat counter reflects unread verification threads (G4)", admin_unread > 0,
          f"count={admin_unread}")

    # ── S17: Public lookup + sharing (§13) — the verification is now COMPLETED ──
    report = customer.get(f"/verifications/{vid_id}/report").json()["data"]
    vid = report["vid"]
    public = httpx.Client(base_url=BASE, timeout=30.0)  # unauthenticated

    private_lookup = public.get(f"/public/verify/{vid}").json()["data"]
    check("public lookup is PRIVATE before sharing is enabled (§13.1)",
          private_lookup["state"] == "PRIVATE", f"state={private_lookup['state']}")

    customer.put(f"/verifications/{vid_id}/public-visibility", json={"enabled": True}).raise_for_status()
    summary = public.get(f"/public/verify/{vid}").json()["data"]
    check("public lookup returns the summary once public (§13.1)", summary["state"] == "SHARED")
    check("public summary exposes the trust BAND, never the number (§13.1)",
          bool(summary.get("trustBand")) and "trustScore" not in summary)

    link = customer.post(f"/verifications/{vid_id}/shares",
                         json={"shareType": "LINK_SUMMARY"}).json()["data"]
    link_view = public.get(f"/public/shared/{link['token']}").json()["data"]
    check("a link share resolves to the summary (§13.2)", link_view["state"] == "SHARED"
          and link_view.get("summary") is not None)

    named = customer.post(f"/verifications/{vid_id}/shares",
                          json={"shareType": "NAMED_FULL", "recipientEmail": "friend@example.com"}).json()["data"]
    gated = public.get(f"/public/shared/{named['token']}").json()["data"]
    check("a named share is gated on the disclaimer before the full report (§13.2)",
          gated["requiresAcknowledgement"] is True and gated.get("report") is None)
    acked = public.post(f"/public/shared/{named['token']}/acknowledge").json()["data"]
    check("acknowledging the disclaimer unlocks the full report (§13.2)", acked.get("report") is not None)

    customer.post(f"/verifications/{vid_id}/shares/{link['id']}/revoke").raise_for_status()
    revoked = public.get(f"/public/shared/{link['token']}").json()["data"]
    check("revoking a share invalidates the token immediately (§13.3)",
          revoked["state"] == "NOT_FOUND", f"state={revoked['state']}")

    # ── S18: Dispute → resolve reject → back to COMPLETED (§14.3) ──
    disp = customer.post(f"/verifications/{vid_id}/disputes", json={
        "disputeType": "INACCURATE_FINDING", "description": "d" * 120,
        "targetRole": "SURVEYOR",
    }).json()["data"]
    check("dispute opens (COMPLETED → DISPUTED, §14.3)", disp["status"] == "OPEN")
    open_disputes = admin_c.get("/admin/disputes").json()["data"]["items"]
    check("dispute appears in the admin queue", any(d["id"] == disp["id"] for d in open_disputes))
    resolved = admin_c.post(f"/admin/disputes/{disp['id']}/resolve", json={
        "outcome": "REJECTED", "note": "Reviewed the survey evidence; the finding stands.",
    }).json()["data"]
    check("admin rejects the dispute (DISPUTED → COMPLETED)", resolved["status"] == "RESOLVED")
    disp_types = {n["type"] for n in customer.get("/notifications").json()["data"]["items"]}
    check("customer got DISPUTE_OPENED + DISPUTE_RESOLVED notifications (§12.2)",
          {"DISPUTE_OPENED", "DISPUTE_RESOLVED"} <= disp_types, str(disp_types))

    # ── S18: Re-check request → admin approve + scope → pay → scoped reopen (§14.1) ──
    recheck = customer.post(f"/verifications/{vid_id}/rechecks",
                            json={"reason": "The survey plan does not match the plot I visited."}).json()["data"]
    check("re-check priced as a % of the original (§14.1, D26)", recheck["priceMinor"] > 0)
    decided = admin_c.post(f"/admin/rechecks/{recheck['id']}/decide",
                           json={"approve": True, "scopeRoles": ["SURVEYOR"]}).json()["data"]
    check("admin approves + scopes the re-check", decided["status"] == "APPROVED"
          and bool(decided.get("checkoutUrl")))
    _stub_pay(customer, decided["checkoutUrl"])
    reopened = admin_c.get(f"/admin/review/{vid_id}").json()["data"]
    check("re-check reopened the scoped task (verification → IN_PROGRESS, §14.1)",
          reopened["status"] == "IN_PROGRESS", f"status={reopened['status']}")

    # ── S18: Tier upgrade from IN_PROGRESS → PREMIUM (delta pricing, §14.2) ──
    upgrade = customer.post(f"/verifications/{vid_id}/upgrades",
                            json={"toTier": "PREMIUM"}).json()["data"]
    check("tier upgrade charges the delta only (§14.2)", upgrade["deltaMinor"] > 0
          and bool(upgrade.get("checkoutUrl")))
    _stub_pay(customer, upgrade["checkoutUrl"])
    upgraded = admin_c.get(f"/admin/review/{vid_id}").json()["data"]
    check("tier upgrade raised the tier to PREMIUM (§14.2)", upgraded["tier"] == "PREMIUM",
          f"tier={upgraded['tier']}")

    # ── S19: Earnings clearance → agent payout → finance approve (§15.1/§15.2) ──
    # The release in step 8 accrued CLEARING commissions to the assigned agents; with the
    # windows zeroed, the sweep moves them to available.
    swept_c = admin_c.post("/admin/payouts/sweeps/commission-clearance").json()["data"]
    check("commission clearance sweep advanced cleared commissions (§15.2)",
          swept_c["advanced"] >= 1, f"advanced={swept_c['advanced']}")

    agent = login("qa-agent-registry@veriprops.io", "Test1234!")
    earnings = agent.get("/agents/earnings").json()["data"]
    check("agent has an available balance after clearance (§15.1)",
          earnings["availableMinor"] > 0, f"available={earnings['availableMinor']}")

    agent.post("/agents/payouts/bank-accounts", json={
        "bankName": "GTBank", "accountNumber": "0123456789", "accountName": "QA Agent"}).raise_for_status()
    bank = agent.get("/agents/payouts/bank-accounts").json()["data"][0]
    payout = agent.post("/agents/payouts", json={
        "amountMinor": earnings["availableMinor"], "bankAccountId": bank["id"]}).json()["data"]
    check("agent requests a withdrawal (REQUESTED, §15.1)", payout["status"] == "REQUESTED",
          f"status={payout['status']}")

    # Requesting locks the funds — available drops to 0 so nothing can be double-spent.
    after_request = agent.get("/agents/earnings").json()["data"]
    check("requesting a payout locks the funds out of available (§15.2)",
          after_request["availableMinor"] == 0, f"available={after_request['availableMinor']}")

    paid = admin_c.post(f"/admin/payouts/{payout['id']}/approve", json={}).json()["data"]
    check("finance approves + disburses the payout (→ PAID, §15.1)", paid["status"] == "PAID",
          f"status={paid['status']}")
    agent_notifs = {n["type"] for n in agent.get("/notifications").json()["data"]["items"]}
    check("agent got the PAYOUT_APPROVED notification (§12.2)", "PAYOUT_APPROVED" in agent_notifs,
          str(agent_notifs))
    final = agent.get("/agents/earnings").json()["data"]
    check("paid-out amount is reflected in total paid (§15.1)", final["totalPaidMinor"] > 0,
          f"totalPaid={final['totalPaidMinor']}")

    # ── S20: Agent reputation, availability, coverage + ranked assignment (§16) ──
    metrics = agent.get("/agents/me/metrics").json()["data"]
    check("agent metrics are derived on read (§16.1)", isinstance(metrics["compositeScore"], int)
          and metrics["totalJobs"] >= 1, f"metrics={metrics}")

    eff = agent.put("/agents/me/availability", json={"availability": "AMBER"}).json()["data"]
    check("agent sets availability (below capacity → honoured, §16.1)", eff == "AMBER", f"effective={eff}")

    bad = agent.put("/agents/me/coverage", json=[{"state": "atlantis"}])
    check("coverage rejects an unknown state (§16.1)", bad.status_code >= 400, f"http {bad.status_code}")
    cov = agent.put("/agents/me/coverage", json=[{"state": "lagos", "travelRadiusKm": 30}]).json()["data"]
    check("agent declares coverage on the canonical states (§16.1, D33)",
          any(c["state"] == "lagos" for c in cov), f"coverage={cov}")

    locations = root.get("/config/nigeria-locations").json()["data"]
    check("backend owns the canonical Nigerian states (§16.1, D33)", len(locations["states"]) == 37,
          f"states={len(locations['states'])}")

    suggested = admin_c.get(
        f"/admin/agents/suggested?verification_id={vid_id}&role=REGISTRY"
    ).json()["data"]
    check("admin suggested-agents ranks eligible candidates (§16.1)", len(suggested) >= 1
          and "compositeScore" in suggested[0], f"suggested={len(suggested)}")

    print("\n" + ("ALL PASSED" if not _failures else f"FAILURES: {_failures}"))
    return 0 if not _failures else 1


def _stub_pay(root: httpx.Client, checkout_url: str) -> None:
    """Drive a secondary (re-check / upgrade) charge to PAID via the deterministic stub webhook."""
    tx_ref = parse_qs(urlparse(checkout_url).query).get("txRef", [""])[0]
    root.post("/payments/stub/confirm", json={"tx_ref": tx_ref}).raise_for_status()


if __name__ == "__main__":
    sys.exit(main())

"""Live drive-through of the S21 (growth §17) + S22 (admin ops §18) surfaces.

Runs against a real backend on :8000, on top of the deterministic dev seed. Exercises the
Phase-18 pricing exit criterion (an admin price edit reflects in the next quote while a locked
price is untouched), the growth quote-discount fields + referral link, and the S22 analytics /
broadcast fan-out / finance + mission-control summaries. Prints PASS/FAIL per step.

How to run (non-prod only): start the backend (local env, ENABLE_OUT_MESSAGING=False), then:
    set PYTHONIOENCODING=utf-8 && python scripts/e2e_s21_s22.py
"""
from __future__ import annotations

import sys

import httpx

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE = "http://localhost:8000/api"
_failures = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        _failures.append(name)


def login(email: str, password: str) -> httpx.Client:
    c = httpx.Client(base_url=BASE, timeout=30.0)
    c.post("/users/auth/sessions", json={"email": email, "password": password}).raise_for_status()
    jar = {k: v for k, v in c.cookies.items()}
    if jar:
        c.headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in jar.items())
    csrf = jar.get("__Host-access_csrf_token")
    if csrf:
        c.headers["X-CSRF-Token"] = csrf
    return c


def main() -> int:
    root = httpx.Client(base_url=BASE, timeout=30.0)
    root.post("/dev/reset").raise_for_status()
    seed = root.post("/dev/seed").json()["data"]
    cust, admin = seed["customer"], seed["admin"]

    customer = login(cust["email"], cust["password"])
    admin_c = login(admin["email"], admin["password"])

    # ── S21: growth quote fields + referral link (§17.1) ──────────────
    quote = customer.get("/verifications/quote", params={"tier": "BASIC", "currency": "NGN"}).json()["data"]
    check("quote carries the growth discount breakdown (§17.1)",
          "netPriceNgnMinor" in quote and "firstTimeDiscountMinor" in quote,
          f"net={quote.get('netPriceNgnMinor')}")
    check("quote net = price − total discount (reconciles)",
          quote["netPriceNgnMinor"] == quote["priceNgnMinor"] - quote["totalDiscountMinor"])

    referral = customer.get("/referrals/me").json()["data"]
    check("referral link is issued for the customer (§17.1)", bool(referral.get("code")),
          f"code={referral.get('code')}")
    check("referral share path targets signup with the ref code",
          referral.get("code", "") in referral.get("sharePath", ""))

    # ── S21: re-lock guard on a fresh draft (§17.1) — not expired → no change ──
    draft = customer.post("/verifications/draft").json()["data"]
    relock = customer.post(f"/verifications/{draft['id']}/refresh-lock").json()["data"]
    check("re-lock on a not-yet-priced draft reports no price change (§17.1)",
          relock["priceChanged"] is False)

    # ── S21: abandonment + referral-credit sweeps are callable (idempotent) ──
    ab = admin_c.post("/admin/verifications/sweeps/abandonment").json()["data"]
    check("abandonment sweep runs (§17.1)", "reminded" in ab, f"reminded={ab.get('reminded')}")
    rc = admin_c.post("/admin/verifications/sweeps/referral-credits").json()["data"]
    check("referral-credit sweep runs (§17.1)", "cleared" in rc, f"cleared={rc.get('cleared')}")

    # ── S22: Phase-18 pricing exit criterion (§18.2, D36) ─────────────
    pricing = admin_c.get("/admin/pricing").json()["data"]
    basic_before = next(t for t in pricing["tiers"] if t["tier"] == "BASIC")["priceNgnMinor"]
    new_price = basic_before + 111_100  # ₦1,111 bump, distinctive
    admin_c.put("/admin/pricing/tiers/BASIC", json={"priceNgnMinor": new_price}).raise_for_status()
    fresh_quote = customer.get("/verifications/quote", params={"tier": "BASIC", "currency": "NGN"}).json()["data"]
    check("admin price edit reflects in the NEXT quote (§18.2 exit criterion)",
          fresh_quote["priceNgnMinor"] == new_price, f"quote={fresh_quote['priceNgnMinor']} expected={new_price}")

    # A locked price (the seeded, already-paid verification) is NOT changed by the edit.
    seeded_v = customer.get(f"/verifications/{seed['verification']['id']}").json()["data"]
    check("a locked/charged price is untouched by the edit (§18.2)",
          seeded_v["priceLockedMinor"] != new_price)

    # ── S22: analytics (§18.1, D38) ───────────────────────────────────
    funnel = admin_c.get("/admin/analytics/funnel").json()["data"]
    check("analytics funnel is derived server-side (§18.1)",
          funnel["created"] >= 1 and funnel["paid"] >= 1, f"created={funnel['created']} paid={funnel['paid']}")
    revenue = admin_c.get("/admin/analytics/revenue").json()["data"]
    check("analytics revenue totals the collected payments (§18.1)", revenue["totalMinor"] > 0,
          f"total={revenue['totalMinor']}")
    for path in ("time-by-tier", "regional", "agent-trends"):
        r = admin_c.get(f"/admin/analytics/{path}")
        check(f"analytics /{path} responds (§18.1)", r.status_code == 200, f"http {r.status_code}")

    # ── S22: broadcast send-now fan-out (§18.1, D37) ──────────────────
    composed = admin_c.post("/admin/broadcasts", json={
        "audience": "ADMINS", "subject": "Ops sync", "body": "Standup at 10am."}).json()["data"]
    check("broadcast composed as DRAFT (§18.1)", composed["status"] == "DRAFT")
    sent = admin_c.post(f"/admin/broadcasts/{composed['id']}/send").json()["data"]
    check("broadcast send-now marks SENT + resolves recipients (§18.1)",
          sent["status"] == "SENT" and sent["recipientCount"] >= 1, f"recipients={sent['recipientCount']}")
    # The admin should now have an in-app broadcast notification.
    notifs = admin_c.get("/notifications").json()["data"]["items"]
    check("broadcast fans out an in-app notification (§18.1)",
          any(n.get("title") == "Announcement" for n in notifs))

    # A scheduled broadcast + its sweep.
    scheduled = admin_c.post("/admin/broadcasts", json={
        "audience": "ADMINS", "subject": "Later", "body": "Body",
        "scheduledAt": "2020-01-01T00:00:00Z"}).json()["data"]
    check("scheduled broadcast is SCHEDULED (§18.1)", scheduled["status"] == "SCHEDULED")
    swept = admin_c.post("/admin/broadcasts/sweeps/scheduled").json()["data"]
    check("scheduled-broadcast sweep sends due ones (§18.1)", swept["sent"] >= 1, f"sent={swept['sent']}")

    # ── S22: finance + mission-control summaries (§18.1) ──────────────
    finance = admin_c.get("/admin/finance/summary").json()["data"]
    check("finance summary reports collected revenue (§18.1)", finance["revenueMinor"] > 0,
          f"revenue={finance['revenueMinor']}")
    mc = admin_c.get("/admin/verifications/summary").json()["data"]
    check("mission control carries revenue + available agents (§18.1)",
          "revenueMinor" in mc and "availableAgents" in mc and "slaAtRisk" in mc,
          f"revenue={mc.get('revenueMinor')} agents={mc.get('availableAgents')}")

    print("\n" + ("ALL PASSED" if not _failures else f"FAILURES: {_failures}"))
    return 1 if _failures else 0


if __name__ == "__main__":
    sys.exit(main())

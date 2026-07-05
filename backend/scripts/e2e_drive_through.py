"""Live end-to-end drive-through of the S15/S16 communication + notification stack.

Runs against a real backend on :8000. Exercises: dev reset+seed, customer login, the §4.7
fraud fast-lane + hold, admin hold-review approve, release → §12.2 status/report notifications
+ §11.1 status auto-post, the SLA-breach sweep (customer + admin, G3), and the admin shared-inbox
Chat counter (G4). Prints PASS/FAIL per step; exits non-zero on any failure.

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

    print("\n" + ("ALL PASSED" if not _failures else f"FAILURES: {_failures}"))
    return 0 if not _failures else 1


if __name__ == "__main__":
    sys.exit(main())

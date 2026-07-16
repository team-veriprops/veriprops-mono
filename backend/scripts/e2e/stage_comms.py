"""Stage 3 — mediated chat + fraud scan + SLA sweep (S15 §11/§4.7, S16 §12, G3/G4).

Runs while the fresh verification is UNDER_REVIEW (the thread must exist before release so
the §11.1 status auto-post lands in it — asserted in the next stage). The SLA-breach sweep
asserts on the *seeded* verification: it is the deterministically SLA-overdue one; the fresh
verification's due date is in the future.
"""
from __future__ import annotations

from .harness import Ctx, check


def run(ctx: Ctx) -> None:
    customer, admin, vid_id = ctx.customer, ctx.admin, ctx.vid_id

    # 1. Customer opens the customer↔admin thread.
    convo = customer.get(f"/verifications/{vid_id}/chat").json()["data"]
    ctx.conv_id = convo["id"]
    check("customer opened the verification chat thread", bool(ctx.conv_id))

    # 2. A clean message takes the fast lane → DELIVERED.
    clean = customer.post(
        f"/verifications/{vid_id}/chat/messages", json={"body": "Hello, any update on my verification?"}
    ).json()["data"]
    check("clean message delivered immediately (§4.7 fast lane)", clean["state"] == "DELIVERED")

    # 3. A message with a phone number is HELD.
    flagged = customer.post(
        f"/verifications/{vid_id}/chat/messages", json={"body": "please call me on 08031234567"}
    ).json()["data"]
    check("phone-number message held for review (§4.7)", flagged["state"] == "HELD",
          f"state={flagged['state']}")
    check("held sender sees the non-accusatory notice", bool(flagged.get("heldNotice")))

    # 4. Admin finds it in the hold queue and approves it (§11.2).
    held = admin.get("/admin/messages/held").json()["data"]["items"]
    check("held message appears in the admin queue (§11.2)", flagged["id"] in [m["id"] for m in held])
    approved = admin.post(f"/admin/messages/{flagged['id']}/approve").json()["data"]
    check("admin approval delivers the held message", approved["state"] == "DELIVERED")

    # 5. Customer now sees the approved message delivered.
    msgs = customer.get(f"/chat/conversations/{ctx.conv_id}/messages").json()["data"]["items"]
    delivered_bodies = [m["body"] for m in msgs if m["state"] == "DELIVERED"]
    check("customer sees the approved message in the thread",
          any("08031234567" in b for b in delivered_bodies))

    # 5b. A second fraud-held message is REJECTED → BLOCKED, never delivered (§11.2).
    blocked = customer.post(
        f"/verifications/{vid_id}/chat/messages", json={"body": "or whatsapp me at 08099887766"}
    ).json()["data"]
    check("second phone-number message held for review (§4.7)", blocked["state"] == "HELD")
    rejected = admin.post(f"/admin/messages/{blocked['id']}/reject").json()["data"]
    check("admin rejection blocks the held message (HELD → BLOCKED, §11.2)",
          rejected["state"] == "BLOCKED", f"state={rejected['state']}")
    msgs_after = customer.get(f"/chat/conversations/{ctx.conv_id}/messages").json()["data"]["items"]
    check("a blocked message is never delivered to the thread (§11.2)",
          not any("08099887766" in m["body"] and m["state"] == "DELIVERED" for m in msgs_after))

    # 6. Admin shared-inbox Chat counter (G4) — unread customer messages count.
    admin_convos = admin.get("/chat/conversations").json()["data"]
    admin_threads = [c for c in admin_convos if c["verificationId"] == vid_id]
    check("admin sees the verification thread in the shared inbox (§N.3 / G4)", len(admin_threads) > 0)
    admin_unread = admin.get("/chat/unread").json()["data"]["count"]
    check("admin Chat counter reflects unread verification threads (G4)", admin_unread > 0,
          f"count={admin_unread}")

    # 7. SLA-breach sweep → customer AND admin notified (G3, D23). Asserts on the seeded
    #    verification: it is UNDER_REVIEW and 3 days overdue by construction.
    swept = admin.post("/admin/verifications/sweeps/sla-breach").json()["data"]
    check("SLA sweep flagged the overdue verification (D23)", swept["flagged"] >= 1,
          f"flagged={swept['flagged']}")
    cust_types = {n["type"] for n in ctx.seed_customer.get("/notifications").json()["data"]["items"]}
    admin_types = {n["type"] for n in admin.get("/notifications").json()["data"]["items"]}
    check("customer got the SLA_BREACHED notification", "SLA_BREACHED" in cust_types)
    check("admin got the SLA_BREACHED notification (G3)", "SLA_BREACHED" in admin_types)

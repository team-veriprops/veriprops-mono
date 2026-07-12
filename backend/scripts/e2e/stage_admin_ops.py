"""Stage 9 — admin operations & analytics (S22 §18, D36/D37/D38).

The Phase-18 pricing exit criterion (an admin price edit reflects in the NEXT quote while
locked prices stay untouched), the server-derived analytics endpoints, broadcast fan-out
(send-now + scheduled sweep), and the finance + mission-control summaries.
"""
from __future__ import annotations

from .harness import Ctx, check


def run(ctx: Ctx) -> None:
    admin, customer = ctx.admin, ctx.seed_customer

    # ── Phase-18 pricing exit criterion (§18.2, D36) ─────────────
    pricing = admin.get("/admin/pricing").json()["data"]
    basic_before = next(t for t in pricing["tiers"] if t["tier"] == "BASIC")["priceNgnMinor"]
    new_price = basic_before + 111_100  # ₦1,111 bump, distinctive
    admin.put("/admin/pricing/tiers/BASIC", json={"priceNgnMinor": new_price}).raise_for_status()
    fresh_quote = customer.get("/verifications/quote", params={"tier": "BASIC", "currency": "NGN"}).json()["data"]
    check("admin price edit reflects in the NEXT quote (§18.2 exit criterion)",
          fresh_quote["priceNgnMinor"] == new_price,
          f"quote={fresh_quote['priceNgnMinor']} expected={new_price}")

    # The fresh verification's charged price is NOT rewritten by the edit.
    locked = ctx.customer.get(f"/verifications/{ctx.vid_id}").json()["data"]
    check("a locked/charged price is untouched by the edit (§18.2)",
          locked["priceLockedMinor"] != new_price)

    # ── Analytics (§18.1, D38) ───────────────────────────────────
    funnel = admin.get("/admin/analytics/funnel").json()["data"]
    check("analytics funnel is derived server-side (§18.1)",
          funnel["created"] >= 1 and funnel["paid"] >= 1,
          f"created={funnel['created']} paid={funnel['paid']}")
    revenue = admin.get("/admin/analytics/revenue").json()["data"]
    check("analytics revenue totals the collected payments (§18.1)", revenue["totalMinor"] > 0,
          f"total={revenue['totalMinor']}")
    for path in ("time-by-tier", "regional", "agent-trends"):
        r = admin.get(f"/admin/analytics/{path}")
        check(f"analytics /{path} responds (§18.1)", r.status_code == 200, f"http {r.status_code}")

    # ── Broadcast send-now fan-out (§18.1, D37) ──────────────────
    composed = admin.post("/admin/broadcasts", json={
        "audience": "ADMINS", "subject": "Ops sync", "body": "Standup at 10am."}).json()["data"]
    check("broadcast composed as DRAFT (§18.1)", composed["status"] == "DRAFT")
    sent = admin.post(f"/admin/broadcasts/{composed['id']}/send").json()["data"]
    check("broadcast send-now marks SENT + resolves recipients (§18.1)",
          sent["status"] == "SENT" and sent["recipientCount"] >= 1, f"recipients={sent['recipientCount']}")
    notifs = admin.get("/notifications").json()["data"]["items"]
    check("broadcast fans out an in-app notification (§18.1)",
          any(n.get("title") == "Announcement" for n in notifs))

    scheduled = admin.post("/admin/broadcasts", json={
        "audience": "ADMINS", "subject": "Later", "body": "Body",
        "scheduledAt": "2020-01-01T00:00:00Z"}).json()["data"]
    check("scheduled broadcast is SCHEDULED (§18.1)", scheduled["status"] == "SCHEDULED")
    swept = admin.post("/admin/broadcasts/sweeps/scheduled").json()["data"]
    check("scheduled-broadcast sweep sends due ones (§18.1)", swept["sent"] >= 1, f"sent={swept['sent']}")

    # ── Broadcast hardening (§18.1, D37): audience resolution, idempotency, cancel guard ──
    preview = admin.get("/admin/broadcasts/preview", params={"audience": "CUSTOMERS"}).json()["data"]
    check("broadcast preview resolves the CUSTOMERS audience by persona (§18.1)",
          preview["recipientCount"] >= 2, f"recipients={preview['recipientCount']}")
    cust_bc = admin.post("/admin/broadcasts", json={
        "audience": "CUSTOMERS", "subject": "Maintenance window",
        "body": "We will be offline briefly on Sunday."}).json()["data"]
    cust_sent = admin.post(f"/admin/broadcasts/{cust_bc['id']}/send").json()["data"]
    check("CUSTOMERS broadcast fan-out matches the preview (§18.1)",
          cust_sent["recipientCount"] == preview["recipientCount"],
          f"sent to {cust_sent['recipientCount']} vs preview {preview['recipientCount']}")
    for who, c in (("seeded", ctx.seed_customer), ("fresh", ctx.customer)):
        notes = c.get("/notifications").json()["data"]["items"]
        check(f"{who} customer received the CUSTOMERS announcement (§18.1)",
              any(n.get("title") == "Announcement" for n in notes))
    replay = admin.post(f"/admin/broadcasts/{cust_bc['id']}/send").json()["data"]
    seeded_count = len([n for n in ctx.seed_customer.get("/notifications").json()["data"]["items"]
                        if n.get("title") == "Announcement"])
    check("re-sending a SENT broadcast is idempotent — no double fan-out (§18.1)",
          replay["status"] == "SENT" and seeded_count == 1,
          f"announcements={seeded_count}")
    doomed = admin.post("/admin/broadcasts", json={
        "audience": "ADMINS", "subject": "Never", "body": "Cancelled before send",
        "scheduledAt": "2030-01-01T00:00:00Z"}).json()["data"]
    cancelled = admin.post(f"/admin/broadcasts/{doomed['id']}/cancel").json()["data"]
    check("scheduled broadcast cancels (§18.1)", cancelled["status"] == "CANCELLED")
    dead_send = admin.post(f"/admin/broadcasts/{doomed['id']}/send")
    check("a cancelled broadcast refuses to send (§18.1 guard)", dead_send.status_code >= 400,
          f"http {dead_send.status_code}")

    # ── Finance + mission-control summaries (§18.1) ──────────────
    finance = admin.get("/admin/finance/summary").json()["data"]
    check("finance summary reports collected revenue (§18.1)", finance["revenueMinor"] > 0,
          f"revenue={finance['revenueMinor']}")
    mc = admin.get("/admin/verifications/summary").json()["data"]
    check("mission control carries revenue + available agents (§18.1)",
          "revenueMinor" in mc and "availableAgents" in mc and "slaAtRisk" in mc,
          f"revenue={mc.get('revenueMinor')} agents={mc.get('availableAgents')}")

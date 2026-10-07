"""Stage 9 — admin operations & analytics (S22 §18, D36/D37/D38).

The Phase-18 pricing exit criterion (an admin price edit reflects in the NEXT quote while
locked prices stay untouched), the server-derived analytics endpoints, broadcast fan-out
(send-now + scheduled sweep), and the finance + mission-control summaries.
"""
from __future__ import annotations

from .harness import QA_PASSWORD, Ctx, check, login, login_status, signup_fresh_user, skip_unless_ci


def run(ctx: Ctx) -> None:
    admin, customer = ctx.admin, ctx.seed_customer

    # ── Phase-18 pricing exit criterion (§18.2, D36) ─────────────
    pricing = admin.get("/admin/pricing").json()["data"]
    basic = next(t for t in pricing["tiers"] if t["tier"] == "BASIC")
    basic_before = basic["priceNgnMinor"]
    basic_items = _restorable_items(basic)
    new_price = basic_before + 111_100  # ₦1,111 bump, distinctive
    # The price and its breakdown are one edit (§18.1): the bump carries a breakdown that adds up.
    admin.put("/admin/pricing/tiers/BASIC", json={
        "priceNgnMinor": new_price,
        "lineItems": [{"label": "Verification service fee", "amountMinor": new_price}],
    }).raise_for_status()
    fresh_quote = customer.get("/verifications/quote", params={"tier": "BASIC", "currency": "NGN"}).json()["data"]
    check("admin price edit reflects in the NEXT quote (§18.2 exit criterion)",
          fresh_quote["priceNgnMinor"] == new_price,
          f"quote={fresh_quote['priceNgnMinor']} expected={new_price}")

    # A price that would leave BASIC's agent commission above the margin is refused (§20.1/D97).
    cut = admin.put("/admin/pricing/tiers/BASIC", json={"priceNgnMinor": 100})
    still = next(t for t in admin.get("/admin/pricing").json()["data"]["tiers"]
                 if t["tier"] == "BASIC")["priceNgnMinor"]
    check("a price cut below the commission margin is refused and changes nothing (§20.1/D97)",
          cut.status_code == 422 and still == new_price, f"http {cut.status_code} price={still}")

    # The fresh verification's charged price is NOT rewritten by the edit.
    locked = ctx.customer.get(f"/verifications/{ctx.vid_id}").json()["data"]
    check("a locked/charged price is untouched by the edit (§18.2)",
          locked["priceLockedMinor"] != new_price)

    # Put the price back: /dev/reset keeps pricing, so a bump left here outlives the run.
    restored = admin.put("/admin/pricing/tiers/BASIC",
                         json={"priceNgnMinor": basic_before, "lineItems": basic_items})
    back = next(t for t in admin.get("/admin/pricing").json()["data"]["tiers"]
                if t["tier"] == "BASIC")["priceNgnMinor"]
    check("the BASIC price is restored after the pricing checks",
          restored.status_code == 200 and back == basic_before, f"price={back} expected={basic_before}")

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
    check("scheduled-broadcast sweep starts due ones and fans them out (§18.1)",
          swept["started"] >= 1 and swept["pages"] >= 1, str(swept))
    after_sweep = admin.get(f"/admin/broadcasts/{scheduled['id']}").json()["data"]
    check("a small scheduled broadcast is SENT once its pages are out, with nothing left to do (§18.1)",
          after_sweep["status"] == "SENT" and after_sweep["allowedActions"] == []
          and after_sweep["recipientsEnqueued"] == after_sweep["recipientCount"] >= 1, str(after_sweep))

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
    _check_broadcast_email_is_queued_then_drained(ctx, admin)
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

    _user_directory(ctx)
    _verification_list_and_notes(ctx)
    _trust_score_weights(admin)
    _line_items(admin, customer)


def _user_directory(ctx: Ctx) -> None:
    """Admin user management on a throwaway customer (§4.2): find, inspect, suspend, reactivate,
    set trust, force a password reset."""
    admin = ctx.admin
    user, email = signup_fresh_user("qa-directory")
    listed = admin.get("/users/admins/users", params={"query": email}).json()["data"]
    check("the user directory finds an account by email, server-side (§4.2)",
          [u["email"] for u in listed["items"]] == [email], f"items={[u['email'] for u in listed['items']]}")
    user_id = listed["items"][0]["id"] if listed["items"] else ""
    detail = admin.get(f"/users/admins/users/{user_id}").json()["data"]
    check("the user detail carries the account's activity (§4.2)",
          detail["email"] == email and detail["verificationsTotal"] == 0 and detail["accountStatus"] == "ACTIVE",
          f"detail={ {k: detail.get(k) for k in ('email', 'verificationsTotal', 'accountStatus')} }")

    suspended = admin.post(f"/users/admins/users/{user_id}/suspend", json={"reason": "Suspected shared login."})
    check("an admin suspends an account (§4.2)", suspended.status_code == 200, f"http {suspended.status_code}")
    check("a suspended account cannot sign in (§4.2)", login_status(email, QA_PASSWORD) != 200)
    check("its live session can no longer refresh (§4.2)",
          user.post("/users/auth/sessions/current").status_code == 401)
    admin.post(f"/users/admins/users/{user_id}/reactivate").raise_for_status()
    check("a reactivated account signs in again (§4.2)", login_status(email, QA_PASSWORD) == 200)

    target = "TRUSTED" if detail["trustStatus"] == "UNTRUSTED" else "UNTRUSTED"
    trusted = admin.post(f"/users/admins/users/{user_id}/trust-status", json={"trustStatus": target})
    after = admin.get(f"/users/admins/users/{user_id}").json()["data"]
    check("an admin changes an account's trust status (§4.2)",
          trusted.status_code == 200 and after["trustStatus"] == target, f"trust={after['trustStatus']}")
    same = admin.post(f"/users/admins/users/{user_id}/trust-status", json={"trustStatus": target})
    check("setting the status it already has is refused, so the audit trail only records changes",
          same.status_code == 422, f"http {same.status_code}")

    reset = admin.post(f"/users/admins/users/{user_id}/password-reset")
    check("an admin forces a password reset (§4.2)", reset.status_code == 200, f"http {reset.status_code}")
    fresh = login(email, QA_PASSWORD)
    check("the forced reset signs out existing sessions (§4.2)",
          user.post("/users/auth/sessions/current").status_code == 401
          and fresh.get("/users/auth/sessions/current").status_code == 200)


def _verification_list_and_notes(ctx: Ctx) -> None:
    """The admin verification list filters server-side (§6.1); notes land on the case (§6.3)."""
    admin = ctx.admin
    found = admin.get("/admin/verifications", params={"query": ctx.vid}).json()["data"]["items"]
    check("the admin list finds a case by VID (§6.1)", [v["id"] for v in found] == [ctx.vid_id],
          f"found={[v['vid'] for v in found]}")
    by_status = admin.get("/admin/verifications", params={"status": "COMPLETED", "page_size": 100}).json()["data"]["items"]
    check("the status filter is applied by the server (§6.1)",
          bool(by_status) and all(v["status"] == "COMPLETED" for v in by_status),
          f"statuses={sorted({v['status'] for v in by_status})}")
    junk = admin.get("/admin/verifications", params={"status": "NOT_A_STATUS"})
    check("an unknown status filter is refused rather than silently matching nothing",
          junk.status_code == 422, f"http {junk.status_code}")

    note = admin.post(f"/admin/verifications/{ctx.vid_id}/notes",
                      json={"category": "OPERATIONAL", "body": "Called the customer about access.", "pinned": True})
    notes = note.json()["data"]["notes"] if note.status_code == 200 else []
    check("an admin note is added to the case, pinned (§6.3)",
          any(n["body"] == "Called the customer about access." and n["pinned"] for n in notes),
          f"http {note.status_code}")


def _trust_score_weights(admin) -> None:
    """Per-tier trust-score weights must sum to 100 (§8.3)."""
    tiers = admin.get("/admin/trust-score-weights").json()["data"]
    basic = next(t for t in tiers if t["tier"] == "BASIC")
    check("each tier's weights are listed and valid (§8.3)", basic["valid"] and basic["totalPercent"] == 100,
          f"basic={basic}")
    current = {w["role"]: w["weightPercent"] for w in basic["weights"]}
    bad = dict(current)
    first = next(iter(bad))
    bad[first] += 1
    refused = admin.put("/admin/trust-score-weights/BASIC", json={"weights": bad})
    check("weights that do not sum to 100 are refused (§8.3)", refused.status_code == 422,
          f"http {refused.status_code}")
    kept = admin.put("/admin/trust-score-weights/BASIC", json={"weights": current}).json()["data"]
    check("saving a valid map keeps the tier valid (§8.3)", kept["valid"] and kept["totalPercent"] == 100)


def _restorable_items(tier: dict) -> list:
    """The tier's line items in the shape a save takes, so the run can put them back. Items saved
    before price and breakdown became one edit may not add up to the price, and a save now refuses
    that; such a tier is restored with one item covering the whole price."""
    items = [{"label": li["label"], "amountMinor": li["amountMinor"]} for li in tier["lineItems"]]
    if items and sum(i["amountMinor"] for i in items) != tier["priceNgnMinor"]:
        return [{"label": "Verification service fee", "amountMinor": tier["priceNgnMinor"]}]
    return items


def _line_items(admin, customer) -> None:
    """A tier's itemised breakdown is saved with its price and must add up to it (§18.1); the
    tier is restored afterwards."""
    tier = next(t for t in admin.get("/admin/pricing").json()["data"]["tiers"] if t["tier"] == "STANDARD")
    price = tier["priceNgnMinor"]
    before = {"priceNgnMinor": price, "lineItems": _restorable_items(tier)}
    replacement = [{"label": "Registry search", "amountMinor": price - 200_000},
                   {"label": "Field visit", "amountMinor": 200_000}]
    saved = admin.put("/admin/pricing/tiers/STANDARD",
                      json={"priceNgnMinor": price, "lineItems": replacement}).json()["data"]
    standard = next(t for t in saved["tiers"] if t["tier"] == "STANDARD")
    check("a tier's line items are replaced as a set, in order (§18.1)",
          [(li["label"], li["amountMinor"]) for li in standard["lineItems"]]
          == [("Registry search", price - 200_000), ("Field visit", 200_000)], f"items={standard['lineItems']}")
    mismatched = admin.put("/admin/pricing/tiers/STANDARD", json={
        "priceNgnMinor": price + 100_000, "lineItems": replacement})
    after = next(t for t in admin.get("/admin/pricing").json()["data"]["tiers"] if t["tier"] == "STANDARD")
    check("line items that do not add up to the price are refused, and change nothing (§18.1)",
          mismatched.status_code == 422 and after["priceNgnMinor"] == price,
          f"http {mismatched.status_code} price={after['priceNgnMinor']}")
    admin.put("/admin/pricing/tiers/STANDARD", json=before).raise_for_status()


def _check_broadcast_email_is_queued_then_drained(ctx: Ctx, admin) -> None:
    """A broadcast's email is queued for the message drain, never sent inside the fan-out
    (`delivery=QUEUED`): the row is PENDING with a due time, and the drain sends it."""
    def latest() -> dict:
        return ctx.root.get("/dev/messages/latest", params={"recipient": ctx.customer_email}).json()["data"]

    queued = latest()
    if not queued.get("found"):
        skip_unless_ci("no outbound message rows — broadcast queue checks skipped",
                       "run the backend with ENABLE_OUT_MESSAGING=True to cover queued delivery")
        return
    check("a broadcast email is queued, not sent in the request (§18.1, delivery=QUEUED)",
          queued["status"] == "pending" and queued["next_retry_at_set"], str(queued))
    drained = admin.post("/messages/sweeps/retries").json()["data"]
    check("the message drain sends queued emails (§18.1)", drained["processed"] >= 1, str(drained))
    sent = latest()
    check("…and the queued broadcast email is now SENT", sent["id"] == queued["id"] and sent["status"] == "sent",
          str(sent))

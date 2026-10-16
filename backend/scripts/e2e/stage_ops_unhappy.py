"""Stage 13 — pool mechanics, admin lifecycle, closing a paid case through Finance, chargeback (S10 §6, §11.3, §8.5).

All destructive work happens on the seeded "ops" verification (crafted task deadlines) and
the seed payment — never on the primary scenario — so the SLA-sweep, analytics, and payout
assertions elsewhere stay unperturbed. Runs after stage_admin_ops for the same reason.
"""
from __future__ import annotations

import uuid

from .harness import Ctx, check, consent_version_for, stub_pay


# ₦5,000 — small enough to leave every tier its minimum margin on the seeded prices.
# ₦3,000: under the seeded 25% discount cap, ₦5,000 across Standard's three roles would leave it
# below the 30% margin on what it collects, and the guard would refuse it.
_REMOTE_BONUS = 300_000


def _ops_task(ctx: Ctx, role: str) -> dict:
    """Admin view of an ops-verification task (agent projections hide pool internals)."""
    review = ctx.admin.get(f"/admin/review/{ctx.seed['ops']['id']}").json()["data"]
    return next(t for t in review["tasks"] if t["role"] == role)


def _submitted_case(ctx: Ctx, address: str) -> dict:
    """A fresh SUBMITTED case for the seeded customer, not yet paid."""
    case = ctx.seed_customer.post("/verifications/draft").json()["data"]
    ctx.seed_customer.post(f"/verifications/{case['id']}/submit", json={
        "property": {"property_type": "LAND", "address": address,
                     "state": "Lagos", "lga": "Eti-Osa", "landmark": "Test"},
        "tier": "BASIC", "currency": "NGN",
        "consent": {"consent_version": consent_version_for("VERIFICATION_TERMS")},
    }).raise_for_status()
    return case


def run(ctx: Ctx) -> None:
    admin, ops = ctx.admin, ctx.seed["ops"]
    ops_id = ops["id"]

    # 1. No-show sweep (§11.4): the seeded REGISTRY assignment blew its accept deadline.
    #
    # The assertions are on the **outcome**, not on this call's reclaim count. The same
    # sweep also runs on a 15-minute APScheduler interval, so on a long-lived server the
    # background job can reclaim the seeded task seconds before this request arrives —
    # leaving a correct system reporting `reclaimed=0`. The property under test is that an
    # unaccepted assignment gets reclaimed, not that this particular caller did it.
    swept = admin.post("/admin/verifications/sweeps/no-show").json()["data"]
    check("no-show sweep endpoint responds (§11.4)", "reclaimed" in swept, f"body={swept}")
    reg = _ops_task(ctx, "REGISTRY")
    check("an unaccepted assignment is reclaimed to PENDING with a decline strike (§11.4)",
          reg["state"] == "PENDING" and reg["declineCount"] >= 1,
          f"state={reg['state']} declines={reg['declineCount']} sweep={swept}")

    # 2. Pool-starvation sweep (§11.4): the seeded FIELD pool window expired unclaimed.
    # Same reasoning — assert the task left the pool, not who pushed it out. The remote bonus
    # is admin config (§20.1 / D97): set it first, so the escalated task carries it.
    bonus_key = "/admin/config/settings/remote_job_bonus_ngn_kobo"
    greedy = admin.put(bonus_key, json={"value": 10_000_000})
    check("a remote bonus that would eat a tier's minimum margin is refused (§20.1/D97)",
          greedy.status_code == 422 and "remote bonuses" in greedy.json()["error"]["message"],
          f"http {greedy.status_code}")
    admin.put(bonus_key, json={"value": _REMOTE_BONUS}).raise_for_status()
    starved = admin.post("/admin/verifications/sweeps/pool-starvation").json()["data"]
    check("pool-starvation sweep endpoint responds (§11.4)", "escalated" in starved,
          f"body={starved}")
    fld = _ops_task(ctx, "FIELD")
    check("an expired pool task leaves the pool for targeted assignment (§11.3)",
          fld["inPool"] is False, f"in_pool={fld['inPool']} sweep={starved}")
    detail_tasks = admin.get(f"/admin/verifications/{ops['id']}").json()["data"]["tasks"]
    fld_bonus = next(t for t in detail_tasks if t["role"] == "FIELD").get("remoteBonusMinor")
    check("the escalated task carries the admin-set remote bonus (§11.4/§20.1)",
          fld_bonus == _REMOTE_BONUS, f"remoteBonusMinor={fld_bonus}")
    self_serve = ctx.agent("FIELD").post(f"/agents/tasks/{fld['id']}/accept")
    check("an escalated task waits for an admin to target it; no agent self-accepts it (§11.3)",
          self_serve.status_code == 422 and "admin" in self_serve.json()["error"]["message"],
          f"http {self_serve.status_code}")
    admin.put(bonus_key, json={"value": 0}).raise_for_status()  # config outlives the run too

    # 3. Decline → back to pool → first-accept-wins re-claim (§12.1).
    surveyor = ctx.agent("SURVEYOR")
    s_id = ops["tasks"]["SURVEYOR"]
    declined = surveyor.post(f"/agents/tasks/{s_id}/decline",
                             json={"reason": "Out of coverage this week."}).json()["data"]
    check("agent decline returns the task to the open pool (§12.1)",
          declined["state"] == "PENDING" and declined["inPool"] is True,
          f"state={declined['state']}")
    srv = _ops_task(ctx, "SURVEYOR")
    check("decline registers a strike on the task (§12.1)", srv["declineCount"] >= 1,
          f"declines={srv['declineCount']}")
    # The pool is first-accept-wins, but only among agents who qualify (§11.3).
    not_agent = ctx.seed_customer.post(f"/agents/tasks/{s_id}/accept")
    check("a customer can't take a pool task by its id (§11.3)",
          not_agent.status_code == 422 and "approved agent" in not_agent.json()["error"]["message"],
          f"http {not_agent.status_code}")
    wrong_role = ctx.agent("REGISTRY").post(f"/agents/tasks/{s_id}/accept")
    check("an agent not cleared for the role can't take its pool task (§11.3/§3.3a)",
          wrong_role.status_code == 422 and "SURVEYOR" in wrong_role.json()["error"]["message"],
          f"http {wrong_role.status_code}")
    still = _ops_task(ctx, "SURVEYOR")
    check("those refusals leave the task in the pool", still["inPool"] is True and still["state"] == "PENDING",
          f"state={still['state']} in_pool={still['inPool']}")
    reclaimed = surveyor.post(f"/agents/tasks/{s_id}/accept").json()["data"]
    check("pooled task is claimed first-accept-wins (§12.1)",
          reclaimed["state"] == "ACCEPTED" and reclaimed["inPool"] is False)

    # 4. Admin lifecycle (§6.1): pause/resume flag, SLA delay. Responses are
    # VerificationDetailDto — the aggregate fields live under `summary`.
    paused = admin.post(f"/admin/verifications/{ops_id}/pause").json()["data"]["summary"]
    check("admin pauses the verification (§6.1)", paused["paused"] is True)
    resumed = admin.post(f"/admin/verifications/{ops_id}/resume").json()["data"]["summary"]
    check("admin resumes the verification (§6.1)", resumed["paused"] is False)

    before_due = admin.get(f"/admin/verifications/{ops_id}").json()["data"]["summary"]["slaDueDate"]
    delayed = admin.post(f"/admin/verifications/{ops_id}/delay",
                         json={"extraBusinessDays": 2, "reason": "Registry office strike."}
                         ).json()["data"]["summary"]
    check("admin extends the SLA by business days (§6.1)",
          delayed["slaDueDate"] and delayed["slaDueDate"] > before_due,
          f"{before_due} → {delayed['slaDueDate']}")

    # 5. Cancel — only legal before completion (§6.1): a throwaway SUBMITTED draft.
    throwaway = _submitted_case(ctx, "1 Cancel Close, Ajah")
    cancelled = admin.post(f"/admin/verifications/{throwaway['id']}/cancel",
                           json={"reason": "Customer requested withdrawal."}).json()["data"]["summary"]
    check("admin cancels a pre-completion verification (§6.1)",
          cancelled["status"] == "CANCELLED", f"status={cancelled['status']}")

    # 5b. A paid case is CLOSED, never cancelled (§6.4): the PRD refund table decides the
    # refund, the case waits on hold, and Finance approves before any money moves (§8.5).
    paid_case = _submitted_case(ctx, "2 Cancel Close, Ajah")
    charge = ctx.seed_customer.post(f"/payments/initiate/{paid_case['id']}", json={"method": "CARD"}).json()["data"]
    stub_pay(ctx.seed_customer, charge["checkoutUrl"])
    refused = admin.post(f"/admin/verifications/{paid_case['id']}/cancel", json={"reason": "Customer withdrew."})
    check("a paid case cannot be cancelled — it is closed instead (§6.4)", refused.status_code >= 400,
          f"status={refused.status_code}")

    quote = admin.get(f"/admin/verifications/{paid_case['id']}/closure-quote",
                      params={"reason": "CUSTOMER_WITHDREW"}).json()["data"]
    check("the closure quote applies the withdrawal surcharge before work starts (PRD refund table)",
          0 < quote["refundMinor"] < charge["amountMinor"] and quote["requiresApproval"]
          and quote["resultingStatus"] == "CANCELLED", f"quote={quote}")
    held = admin.post(f"/admin/verifications/{paid_case['id']}/close",
                      json={"reason": "CUSTOMER_WITHDREW", "note": "Customer withdrew before any work."}).json()["data"]
    detail = admin.get(f"/admin/verifications/{paid_case['id']}").json()["data"]
    check("closing with money owed puts the case on hold, nothing refunded yet",
          held["onHold"] and held["refundMinor"] == quote["refundMinor"] and detail["onHold"]
          and detail["summary"]["status"] == "PAID" and all(p["status"] == "SUCCEEDED" for p in detail["payments"]),
          f"held={held} status={detail['summary']['status']}")
    queue = admin.get("/admin/refund-requests", params={"status": "PENDING"}).json()["data"]["items"]
    check("the refund waits in Finance's queue (§8.5)",
          any(r["id"] == held["refundRequestId"] and r["amountMinor"] == quote["refundMinor"] for r in queue),
          f"queue={[(r['vid'], r['amountMinor']) for r in queue]}")
    unexplained = admin.post(f"/admin/refund-requests/{held['refundRequestId']}/reject", json={})
    check("Finance must say why it rejects a refund", unexplained.status_code >= 400,
          f"status={unexplained.status_code}")
    admin.post(f"/admin/refund-requests/{held['refundRequestId']}/reject",
               json={"note": "The customer asked to continue after all."}).raise_for_status()
    resumed = admin.get(f"/admin/verifications/{paid_case['id']}").json()["data"]
    check("a rejected refund lifts the hold and sends nothing",
          not resumed["onHold"] and resumed["summary"]["status"] == "PAID"
          and all(p["status"] == "SUCCEEDED" for p in resumed["payments"]), f"detail={resumed['summary']}")

    duplicate = admin.post(f"/admin/verifications/{paid_case['id']}/close",
                           json={"reason": "DUPLICATE", "note": "Paid twice for the same plot."}).json()["data"]
    decided = admin.post(f"/admin/refund-requests/{duplicate['refundRequestId']}/approve",
                         json={"note": "Checked the duplicate."}).json()["data"]
    closed = admin.get(f"/admin/verifications/{paid_case['id']}").json()["data"]
    check("Finance's approval closes the case and refunds it in full",
          decided["outcome"]["refundedMinor"] == charge["amountMinor"]
          and closed["summary"]["status"] == "CANCELLED" and closed["refundableMinor"] == 0
          and all(p["status"] == "REFUNDED" for p in closed["payments"]),
          f"outcome={decided['outcome']} status={closed['summary']['status']}")
    listed = admin.get("/admin/payments", params={"query": paid_case["vid"], "status": "REFUNDED"}).json()["data"]
    check("finance's payments list finds that charge by VID, refunded",
          [(p["vid"], p["status"], p["refundedAmountMinor"]) for p in listed["items"]]
          == [(paid_case["vid"], "REFUNDED", charge["amountMinor"])],
          f"items={listed['items']}")
    by_amount = admin.get("/admin/payments", params={"order_by": "amountMinor asc", "page_size": 50}).json()["data"]
    amounts = [p["amountMinor"] for p in by_amount["items"]]
    check("finance's payments list sorts server-side by a column the client picks",
          amounts == sorted(amounts) and by_amount["meta"]["sort"] == "amountMinor asc"
          and "amountMinor" in by_amount["meta"]["sortableFields"],
          f"sort={by_amount['meta'].get('sort')} amounts={amounts[:5]}")
    unsorted = admin.get("/admin/payments", params={"order_by": "customerId asc"}).json()["data"]
    check("a sort outside the list's allowlist falls back to newest first",
          unsorted["meta"]["sort"] == "dateCreated desc", f"sort={unsorted['meta'].get('sort')}")
    # The stub gateway never refuses a refund, so nothing waits to be retried — and a retry
    # of a charge that owes nothing is refused rather than sending money twice.
    retries = admin.get("/admin/payments/refund-retries").json()["data"]
    check("nothing waits in the refunds-to-retry list when every refund landed (§8.5)",
          all(p["id"] != listed["items"][0]["id"] for p in retries["items"]) if listed["items"] else False,
          f"retries={retries['meta']}")
    refunded_id = listed["items"][0]["id"] if listed["items"] else "missing"
    retry = admin.post(f"/admin/payments/{refunded_id}/refund")
    check("retrying a refund on a charge that owes nothing is refused (§8.5)", 400 <= retry.status_code < 500,
          f"http {retry.status_code}: {retry.text[:120]}")

    # 5c. A charge that settles after its case was cancelled mid-payment: the case stays
    # cancelled, and the whole charge waits for Finance as a late-charge refund.
    late_case = _submitted_case(ctx, "3 Cancel Close, Ajah")
    late_charge = ctx.seed_customer.post(f"/payments/initiate/{late_case['id']}", json={"method": "CARD"}).json()["data"]
    admin.post(f"/admin/verifications/{late_case['id']}/cancel",
               json={"reason": "Customer asked to stop mid-payment."}).raise_for_status()
    stub_pay(ctx.seed_customer, late_charge["checkoutUrl"])
    pending = admin.get("/admin/refund-requests", params={"status": "PENDING"}).json()["data"]["items"]
    late = next((r for r in pending if r["vid"] == late_case["vid"]), None)
    after = admin.get(f"/admin/verifications/{late_case['id']}").json()["data"]
    check("a late charge on a cancelled case is filed for Finance, and the case stays cancelled",
          late is not None and late["source"] == "LATE_CHARGE" and late["amountMinor"] == late_charge["amountMinor"]
          and after["summary"]["status"] == "CANCELLED", f"late={late} status={after['summary']['status']}")
    admin.post(f"/admin/refund-requests/{late['id']}/approve", json={}).raise_for_status()
    refunded = admin.get(f"/admin/verifications/{late_case['id']}").json()["data"]
    check("approving the late charge refunds it", all(p["status"] == "REFUNDED" for p in refunded["payments"]),
          f"payments={[p['status'] for p in refunded['payments']]}")

    # 6. We cannot deliver (§8.5): closed as FAILED, refunded in full once Finance approves.
    failing = admin.post(f"/admin/verifications/{ops_id}/close", json={
        "reason": "CANNOT_DELIVER", "note": "Property could not be located at the stated address.",
    }).json()["data"]
    admin.post(f"/admin/refund-requests/{failing['refundRequestId']}/approve", json={}).raise_for_status()
    detail = admin.get(f"/admin/verifications/{ops_id}").json()["data"]
    check("closing because we cannot deliver fails the case once Finance approves (§8.5)",
          detail["summary"]["status"] == "FAILED", f"status={detail['summary']['status']}")
    payments = detail.get("payments") or []
    check("failing refunds the collected payment (§8.5)",
          any(p.get("status") == "REFUNDED" for p in payments),
          f"payments={[p.get('status') for p in payments]}")
    check("the case's unfinished tasks are cancelled, freeing their agents",
          all(t["state"] in ("SUBMITTED", "APPROVED", "CANCELLED") for t in detail["tasks"]),
          f"tasks={[t['state'] for t in detail['tasks']]}")

    # 7. Chargeback (§6a): flag (stub webhook) → idempotent replay → rebuttal → LOST clawback.
    event_id = f"evt-{uuid.uuid4().hex[:10]}"
    seed_tx_ref = f"{ctx.seed['verification']['vid']}-SEED"
    flagged = admin.post("/payments/chargebacks/stub/flag",
                         json={"eventId": event_id, "txRef": seed_tx_ref,
                               "reason": "fraudulent"}).json()["data"]
    chargeback_id = flagged.get("chargeback_id") or flagged.get("chargebackId")
    check("stub chargeback webhook flags the payment (§6a)", bool(chargeback_id),
          f"chargeback={chargeback_id}")
    replay = admin.post("/payments/chargebacks/stub/flag",
                        json={"eventId": event_id, "txRef": seed_tx_ref}).json()["data"]
    replay_id = replay.get("chargeback_id") or replay.get("chargebackId")
    check("replaying the same gateway event is idempotent (§4.6)", replay_id == chargeback_id)
    rebutted = admin.post(f"/admin/verifications/chargebacks/{chargeback_id}/rebuttal").json()["data"]
    check("admin submits the rebuttal pack (§6a)", rebutted["status"] == "REBUTTAL_SUBMITTED",
          f"status={rebutted.get('status')}")
    lost = admin.post(f"/admin/verifications/chargebacks/{chargeback_id}/resolve",
                      json={"won": False}).json()["data"]
    check("chargeback LOST records the loss + refund (§6a)", lost["status"] == "LOST",
          f"status={lost.get('status')}")

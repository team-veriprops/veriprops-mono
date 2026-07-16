"""Stage 13 — pool mechanics, admin lifecycle, fail+refund, chargeback (S10 §6, §7.2, §8.5).

All destructive work happens on the seeded "ops" verification (crafted task deadlines) and
the seed payment — never on the primary scenario — so the SLA-sweep, analytics, and payout
assertions elsewhere stay unperturbed. Runs after stage_admin_ops for the same reason.
"""
from __future__ import annotations

import uuid

from .harness import CONSENT_VERSION, Ctx, check


def _ops_task(ctx: Ctx, role: str) -> dict:
    """Admin view of an ops-verification task (agent projections hide pool internals)."""
    review = ctx.admin.get(f"/admin/review/{ctx.seed['ops']['id']}").json()["data"]
    return next(t for t in review["tasks"] if t["role"] == role)


def run(ctx: Ctx) -> None:
    admin, ops = ctx.admin, ctx.seed["ops"]
    ops_id = ops["id"]

    # 1. No-show sweep (§7.2): the seeded REGISTRY assignment blew its accept deadline.
    swept = admin.post("/admin/verifications/sweeps/no-show").json()["data"]
    check("no-show sweep reclaims the unaccepted assignment (§7.2)", swept["reclaimed"] >= 1,
          f"reclaimed={swept['reclaimed']}")
    reg = _ops_task(ctx, "REGISTRY")
    check("reclaimed task returns to PENDING with a decline strike (§7.2)",
          reg["state"] == "PENDING" and reg["declineCount"] >= 1,
          f"state={reg['state']} declines={reg['declineCount']}")

    # 2. Pool-starvation sweep (§7.2): the seeded FIELD pool window expired unclaimed.
    starved = admin.post("/admin/verifications/sweeps/pool-starvation").json()["data"]
    check("pool-starvation sweep escalates the expired pool task (§7.2)",
          starved["escalated"] >= 1, f"escalated={starved['escalated']}")
    fld = _ops_task(ctx, "FIELD")
    check("starved task leaves the pool for targeted assignment (§7.2)",
          fld["inPool"] is False, f"in_pool={fld['inPool']}")

    # 3. Decline → back to pool → first-accept-wins re-claim (§7.1).
    surveyor = ctx.agent("SURVEYOR")
    s_id = ops["tasks"]["SURVEYOR"]
    declined = surveyor.post(f"/agents/tasks/{s_id}/decline",
                             json={"reason": "Out of coverage this week."}).json()["data"]
    check("agent decline returns the task to the open pool (§7.1)",
          declined["state"] == "PENDING" and declined["inPool"] is True,
          f"state={declined['state']}")
    srv = _ops_task(ctx, "SURVEYOR")
    check("decline registers a strike on the task (§7.1)", srv["declineCount"] >= 1,
          f"declines={srv['declineCount']}")
    reclaimed = surveyor.post(f"/agents/tasks/{s_id}/accept").json()["data"]
    check("pooled task is claimed first-accept-wins (§7.1)",
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
    throwaway = ctx.seed_customer.post("/verifications/draft").json()["data"]
    ctx.seed_customer.post(f"/verifications/{throwaway['id']}/submit", json={
        "property": {"property_type": "LAND", "address": "1 Cancel Close, Ajah",
                     "state": "Lagos", "lga": "Eti-Osa", "landmark": "Test"},
        "tier": "BASIC", "currency": "NGN", "consent": {"consent_version": CONSENT_VERSION},
    }).raise_for_status()
    cancelled = admin.post(f"/admin/verifications/{throwaway['id']}/cancel",
                           json={"reason": "Customer requested withdrawal."}).json()["data"]["summary"]
    check("admin cancels a pre-completion verification (§6.1)",
          cancelled["status"] == "CANCELLED", f"status={cancelled['status']}")

    # 6. Fail + refund (§8.5): terminal FAILED, every SUCCEEDED payment refunded.
    failed = admin.post(f"/admin/review/{ops_id}/fail",
                        json={"reason": "Property could not be located at the stated address."}).json()["data"]
    check("admin fails the verification (→ FAILED, §8.5)", failed["status"] == "FAILED")
    detail = admin.get(f"/admin/verifications/{ops_id}").json()["data"]
    payments = detail.get("payments") or []
    check("failing refunds the collected payment (§8.5)",
          any(p.get("status") == "REFUNDED" for p in payments),
          f"payments={[p.get('status') for p in payments]}")

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

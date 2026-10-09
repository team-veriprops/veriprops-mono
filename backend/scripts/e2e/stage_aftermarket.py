"""Stage 7 — disputes, re-checks & upgrades (S18 §14), earnings → payout (S19 §15),
reputation/availability/coverage (S20 §16).

All on the fresh, now-COMPLETED verification. The commission-clearance/reserve windows were
zeroed in the runner prologue, so the commissions accrued at release clear in this run and
the earnings → payout → approval → disbursement flow completes end-to-end, including a
declined transfer that finance retries and then rejects.
"""
from __future__ import annotations

from .harness import Ctx, check, stub_pay

# The stub transfer gateway's documented accounts (main/appodus_utils/integrations/payment/
# gateway/stub.py): one no bank knows, one whose transfers the bank declines.
STUB_UNKNOWN_ACCOUNT = "0000000000"
STUB_DECLINING_ACCOUNT = "0000009999"


def run(ctx: Ctx) -> None:
    customer, admin, vid_id = ctx.customer, ctx.admin, ctx.vid_id

    # ── S18: Dispute → resolve reject → back to COMPLETED (§14.3) ──
    disp = customer.post(f"/verifications/{vid_id}/disputes", json={
        "disputeType": "INACCURATE_FINDING", "description": "d" * 120,
        "targetRole": "SURVEYOR",
    }).json()["data"]
    check("dispute opens (COMPLETED → DISPUTED, §14.3)", disp["status"] == "OPEN")
    open_disputes = admin.get("/admin/disputes").json()["data"]["items"]
    check("dispute appears in the admin queue", any(d["id"] == disp["id"] for d in open_disputes))

    # The disputed agent sees the dispute against their work and answers it (§14.3).
    surveyor = ctx.agent("SURVEYOR")
    agent_open = surveyor.get("/agents/disputes").json()["data"]
    check("the disputed agent sees the dispute against their work (§14.3)",
          any(d["id"] == disp["id"] for d in agent_open), f"disputes={[d['id'] for d in agent_open]}")
    defended = surveyor.post(f"/agents/disputes/{disp['id']}/defence",
                             json={"text": "The plan matches the registry survey; photos attached to the task."})
    check("the agent files a defence (§14.3)", defended.status_code == 200, f"http {defended.status_code}")
    detail = admin.get(f"/admin/disputes/{disp['id']}").json()["data"]
    check("the admin sees the dispute with the agent's defence (§14.3)",
          detail["id"] == disp["id"] and bool(detail.get("agentDefenceText")), f"detail={detail}")
    stranger = ctx.agent("FIELD").post(f"/agents/disputes/{disp['id']}/defence", json={"text": "not mine"})
    check("an agent not on the disputed task cannot answer it (§6a)", stranger.status_code >= 400,
          f"http {stranger.status_code}")

    resolved =admin.post(f"/admin/disputes/{disp['id']}/resolve", json={
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
    queue = admin.get("/admin/rechecks").json()["data"]["items"]
    check("the re-check waits in the admin queue (§14.1)", any(r["id"] == recheck["id"] for r in queue),
          f"queue={[r['id'] for r in queue]}")
    decided = admin.post(f"/admin/rechecks/{recheck['id']}/decide",
                         json={"approve": True, "scopeRoles": ["SURVEYOR"]}).json()["data"]
    check("admin approves + scopes the re-check", decided["status"] == "APPROVED"
          and bool(decided.get("checkoutUrl")))
    stub_pay(customer, decided["checkoutUrl"])
    reopened = admin.get(f"/admin/review/{vid_id}").json()["data"]
    check("re-check reopened the scoped task (verification → IN_PROGRESS, §14.1)",
          reopened["status"] == "IN_PROGRESS", f"status={reopened['status']}")

    # ── S18: Tier upgrade from IN_PROGRESS → PREMIUM (delta pricing, §14.2) ──
    upgrade = customer.post(f"/verifications/{vid_id}/upgrades",
                            json={"toTier": "PREMIUM"}).json()["data"]
    check("tier upgrade charges the delta only (§14.2)", upgrade["deltaMinor"] > 0
          and bool(upgrade.get("checkoutUrl")))
    stub_pay(customer, upgrade["checkoutUrl"])
    upgraded = admin.get(f"/admin/review/{vid_id}").json()["data"]
    check("tier upgrade raised the tier to PREMIUM (§14.2)", upgraded["tier"] == "PREMIUM",
          f"tier={upgraded['tier']}")

    # ── S19: Earnings clearance → agent payout → finance approve (§15.1/§15.2) ──
    # The release accrued CLEARING commissions to the assigned agents; with the windows
    # zeroed in the prologue, the sweep moves them to available.
    swept = admin.post("/admin/payouts/sweeps/commission-clearance").json()["data"]
    check("commission clearance sweep advanced cleared commissions (§15.2)",
          swept["advanced"] >= 1, f"advanced={swept['advanced']}")

    agent = ctx.agent("REGISTRY")
    earnings = agent.get("/agents/earnings").json()["data"]
    check("agent has an available balance after clearance (§15.1)",
          earnings["availableMinor"] > 0, f"available={earnings['availableMinor']}")

    # A beneficiary is picked from the gateway's bank list and named by the bank, never typed.
    banks = agent.get("/agents/payouts/banks").json()["data"]
    check("agent sees the paying gateway's bank list (§15.1)", len(banks) > 0, f"banks={len(banks)}")
    bank_code = banks[0]["code"]
    unknown = agent.post("/agents/payouts/bank-accounts/resolve", json={
        "bankCode": bank_code, "accountNumber": STUB_UNKNOWN_ACCOUNT})
    check("an account the bank does not know is refused (422)", unknown.status_code == 422,
          f"http {unknown.status_code}")
    resolved = agent.post("/agents/payouts/bank-accounts/resolve", json={
        "bankCode": bank_code, "accountNumber": "1234567890"}).json()["data"]
    check("the account name comes from the bank", resolved["accountName"] == "TEST ACCOUNT 7890",
          f"name={resolved['accountName']}")
    good = agent.post("/agents/payouts/bank-accounts", json={
        "bankCode": bank_code, "accountNumber": "1234567890", "accountName": "Typed By Agent"}).json()["data"]
    check("the saved account carries the bank's name, not the typed one",
          good["accountName"] == "TEST ACCOUNT 7890", f"name={good['accountName']}")
    declining = agent.post("/agents/payouts/bank-accounts", json={
        "bankCode": bank_code, "accountNumber": STUB_DECLINING_ACCOUNT}).json()["data"]

    # The transfer fee is quoted before the agent confirms, and comes out of what they receive.
    available = earnings["availableMinor"]
    small = min(200_000, available // 4)
    quote = agent.post("/agents/payouts/quote", json={
        "amountMinor": small, "bankAccountId": declining["id"]}).json()["data"]
    check("the fee is quoted up front and deducted (§15.1)",
          quote["feeMinor"] > 0 and quote["netMinor"] == small - quote["feeMinor"], f"quote={quote}")

    doomed = agent.post("/agents/payouts", json={"amountMinor": small, "bankAccountId": declining["id"]}).json()["data"]
    payout = agent.post("/agents/payouts", json={
        "amountMinor": available - small, "bankAccountId": good["id"]}).json()["data"]
    check("agent requests a withdrawal (REQUESTED, §15.1)", payout["status"] == "REQUESTED",
          f"status={payout['status']}")
    check("the request records the fee and the net amount",
          payout["feeMinor"] > 0 and payout["netMinor"] == payout["amountMinor"] - payout["feeMinor"], str(payout))

    # Requesting locks the funds — available drops to 0 so nothing can be double-spent.
    after_request = agent.get("/agents/earnings").json()["data"]
    check("requesting a payout locks the funds out of available (§15.2)",
          after_request["availableMinor"] == 0, f"available={after_request['availableMinor']}")

    approved = admin.post(f"/admin/payouts/{payout['id']}/approve", json={}).json()["data"]
    check("finance approval queues the payout (→ APPROVED, §15.1)", approved["status"] == "APPROVED",
          f"status={approved['status']}")
    admin.post(f"/admin/payouts/{doomed['id']}/approve", json={}).raise_for_status()
    queue = admin.get("/admin/payouts/disbursement-queue").json()["data"]
    check("the disburse button shows what waits (§15.1)", queue["count"] >= 2
          and queue["totalMinor"] >= available, f"queue={queue}")

    outcome = admin.post("/admin/payouts/disburse").json()["data"]
    check("the batch pays one transfer and records the declined one",
          outcome["paid"] >= 1 and outcome["failed"] >= 1 and outcome["remaining"] == 0, f"outcome={outcome}")
    # Each transfer settles in its own independent transaction, and the agent's email is sent
    # inside it: its bookkeeping row must be found there and marked SENT, not left PENDING.
    mail = ctx.root.get("/dev/messages/latest", params={"recipient": "qa-agent-registry@"}).json()["data"]
    if mail.get("found"):
        check("the payout email sent inside the settlement is recorded as SENT", mail["status"] == "sent",
              str(mail))
    finance_view = {p["id"]: p for p in admin.get("/admin/payouts?page_size=50").json()["data"]["items"]}
    check("the paid transfer is PAID with its reference", finance_view[payout["id"]]["status"] == "PAID"
          and bool(finance_view[payout["id"]]["transferReference"]), str(finance_view[payout["id"]]))
    failed = finance_view[doomed["id"]]
    check("the declined transfer is FAILED, with the bank's reason for finance",
          failed["status"] == "FAILED" and bool(failed["failureReason"])
          and set(failed["allowedActions"]) == {"RETRY", "ADJUST", "REJECT"}, str(failed))

    # A failed transfer keeps its funds reserved until finance decides.
    retried = admin.post(f"/admin/payouts/{doomed['id']}/retry").json()["data"]
    check("finance retries a failed transfer (→ APPROVED)", retried["status"] == "APPROVED", str(retried))
    rejected = admin.post(f"/admin/payouts/{doomed['id']}/reject", json={"note": "account closed"}).json()["data"]
    check("finance rejects it instead (→ REJECTED)", rejected["status"] == "REJECTED", str(rejected))

    agent_notifs = {n["type"] for n in agent.get("/notifications").json()["data"]["items"]}
    check("agent got PAYOUT_APPROVED, PAYOUT_PAID and PAYOUT_REJECTED (§12.2)",
          {"PAYOUT_APPROVED", "PAYOUT_PAID", "PAYOUT_REJECTED"} <= agent_notifs, str(agent_notifs))
    final = agent.get("/agents/earnings").json()["data"]
    check("paid-out amount is reflected in total paid (§15.1)", final["totalPaidMinor"] == available - small,
          f"totalPaid={final['totalPaidMinor']}")
    check("the rejected withdrawal is back in available (§15.1)", final["availableMinor"] == small,
          f"available={final['availableMinor']}")

    jobs = agent.get("/agents/earnings/jobs").json()["data"]
    check("the per-job earnings breakdown lists the commissions behind the balance (§15.1)",
          jobs["meta"]["total"] >= 1 and all(j["amountMinor"] > 0 for j in jobs["items"]), f"jobs={jobs['meta']}")

    # An agent may withdraw a request finance has not touched; finance may hold or adjust one.
    withdrawn = agent.post("/agents/payouts", json={"amountMinor": small, "bankAccountId": good["id"]}).json()["data"]
    cancelled = agent.post(f"/agents/payouts/{withdrawn['id']}/cancel").json()["data"]
    back = agent.get("/agents/earnings").json()["data"]["availableMinor"]
    check("an agent cancels an untouched request and the funds return (§15.1)",
          cancelled["status"] == "CANCELLED" and back == small, f"status={cancelled['status']} available={back}")
    held_request = agent.post("/agents/payouts", json={"amountMinor": small, "bankAccountId": good["id"]}).json()["data"]
    held = admin.post(f"/admin/payouts/{held_request['id']}/hold", json={"note": "Checking the account name."}).json()["data"]
    check("finance holds a payout for review (→ HELD, §15.1)", held["status"] == "HELD", str(held))
    blocked = agent.post(f"/agents/payouts/{held_request['id']}/cancel")
    check("a request finance is holding can no longer be cancelled by the agent", blocked.status_code >= 400,
          f"http {blocked.status_code}")
    adjusted = admin.post(f"/admin/payouts/{held_request['id']}/adjust",
                          json={"adjustmentMinor": 1_000, "note": "Rounding correction."}).json()["data"]
    check("finance records an adjustment without deciding the request (§15.1)",
          adjusted["status"] == "HELD" and adjusted["adjustmentMinor"] == 1_000, str(adjusted))
    admin.post(f"/admin/payouts/{held_request['id']}/reject", json={"note": "Test hold released."}).raise_for_status()
    check("rejecting the held request returns its funds (§15.1)",
          agent.get("/agents/earnings").json()["data"]["availableMinor"] == small)

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
    profile = agent.get("/agents/me/profile").json()["data"]
    check("the agent's profile page brings metrics, availability and coverage together (§16.1)",
          profile["availability"] == "AMBER" and "REGISTRY" in profile["approvedRoles"]
          and any(c["state"] == "lagos" for c in profile["coverage"]), f"profile={profile}")

    locations = ctx.root.get("/config/nigeria-locations").json()["data"]
    check("backend owns the canonical Nigerian states (§16.1, D33)", len(locations["states"]) == 37,
          f"states={len(locations['states'])}")

    suggested = admin.get(
        f"/admin/agents/suggested?verification_id={vid_id}&role=REGISTRY"
    ).json()["data"]
    check("admin suggested-agents ranks eligible candidates (§16.1)", len(suggested) >= 1
          and "compositeScore" in suggested[0], f"suggested={len(suggested)}")

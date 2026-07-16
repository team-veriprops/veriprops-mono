"""Stage 7 — disputes, re-checks & upgrades (S18 §14), earnings → payout (S19 §15),
reputation/availability/coverage (S20 §16).

All on the fresh, now-COMPLETED verification. The commission-clearance/reserve windows were
zeroed in the runner prologue, so the commissions accrued at release clear in this run and
the earnings → payout → finance-approval flow completes end-to-end.
"""
from __future__ import annotations

from .harness import Ctx, check, stub_pay


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
    resolved = admin.post(f"/admin/disputes/{disp['id']}/resolve", json={
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

    paid = admin.post(f"/admin/payouts/{payout['id']}/approve", json={}).json()["data"]
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

    locations = ctx.root.get("/config/nigeria-locations").json()["data"]
    check("backend owns the canonical Nigerian states (§16.1, D33)", len(locations["states"]) == 37,
          f"states={len(locations['states'])}")

    suggested = admin.get(
        f"/admin/agents/suggested?verification_id={vid_id}&role=REGISTRY"
    ).json()["data"]
    check("admin suggested-agents ranks eligible candidates (§16.1)", len(suggested) >= 1
          and "compositeScore" in suggested[0], f"suggested={len(suggested)}")

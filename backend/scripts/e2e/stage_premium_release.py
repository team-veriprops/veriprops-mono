"""Stage 10 — the PREMIUM leg finished: v2 release, declined re-check, upheld dispute → v3.

Continues where stage_aftermarket stops (verification IN_PROGRESS: SURVEYOR reopened by the
paid re-check, tier upgraded to PREMIUM). Drives the reopened task home, unlocks + executes
the LAWYER task (its §2.5 dependency gate needs the other three settled), re-releases →
v2 report, then the two remaining §14 branches: a re-check the admin DECLINES, and a
PARTIAL_RECHECK (upheld) dispute that reopens the LAWYER and produces the v3 RECHECK report.
"""
from __future__ import annotations

from .harness import MINIMAL_PNG, Ctx, check
from .stage_execution import ROLE_PAYLOADS


def _agent_task(ctx: Ctx, role: str) -> dict:
    agent = ctx.agent(role)
    tasks = agent.get("/agents/tasks").json()["data"]["items"]
    return next(t for t in tasks if t["verificationId"] == ctx.vid_id and t["role"] == role)


def run(ctx: Ctx) -> None:
    admin, customer, vid_id = ctx.admin, ctx.customer, ctx.vid_id

    # 1. The recheck-reopened SURVEYOR task is IN_PROGRESS with its evidence intact — resubmit.
    surveyor = ctx.agent("SURVEYOR")
    s_task = _agent_task(ctx, "SURVEYOR")
    check("recheck-reopened SURVEYOR task is back with the agent (§14.1)",
          s_task["state"] == "IN_PROGRESS", f"state={s_task['state']}")
    resubmitted = surveyor.post(f"/agents/tasks/{s_task['id']}/submit",
                                json={"payload": ROLE_PAYLOADS["SURVEYOR"]}).json()["data"]
    check("SURVEYOR resubmits the scoped re-check work (§14.1)", resubmitted["state"] == "SUBMITTED")
    admin.post(f"/admin/review/{vid_id}/tasks/SURVEYOR/approve", json={"quality": 90}).raise_for_status()

    # 2. LAWYER unlocks once the other three are settled (§2.5 dependency gate) — full cycle.
    lawyer_id = ctx.seed["agents"]["LAWYER"]
    r = admin.post(f"/admin/verifications/{vid_id}/tasks/LAWYER/assign", json={"agentId": lawyer_id})
    check("PREMIUM upgrade unlocks the LAWYER assignment (§2.5/§14.2)", r.status_code == 200,
          f"http {r.status_code}: {r.text[:180]}")
    lawyer = ctx.agent("LAWYER")
    l_task = _agent_task(ctx, "LAWYER")
    ctx.task_ids["LAWYER"] = l_task["id"]
    lawyer.post(f"/agents/tasks/{l_task['id']}/accept").raise_for_status()
    lawyer.post(f"/agents/tasks/{l_task['id']}/start").raise_for_status()
    lawyer.post(
        f"/agents/tasks/{l_task['id']}/evidence",
        files={"file": ("legal-opinion.png", MINIMAL_PNG, "image/png")},
        data={"kind": "DOCUMENT"},
    ).raise_for_status()
    submitted = lawyer.post(f"/agents/tasks/{l_task['id']}/submit",
                            json={"payload": ROLE_PAYLOADS["LAWYER"]}).json()["data"]
    check("LAWYER executes and submits the legal-opinion task (§12.2)",
          submitted["state"] == "SUBMITTED")
    admin.post(f"/admin/review/{vid_id}/tasks/LAWYER/approve", json={"quality": 95}).raise_for_status()

    # 3. Re-release → the v2 report supersedes v1 (§8.4/§14).
    released = admin.post(f"/admin/review/{vid_id}/release",
                          json={"reason": "Re-check and upgrade work verified."}).json()["data"]
    check("re-release completes the PREMIUM verification (→ COMPLETED)",
          released["status"] == "COMPLETED", f"status={released['status']}")
    check("re-release produces the v2 report (§8.4)",
          released["report"] is not None and released["report"]["reportVersion"] >= 2,
          f"version={released['report'] and released['report']['reportVersion']}")
    v2_version = released["report"]["reportVersion"]
    report = customer.get(f"/verifications/{vid_id}/report").json()["data"]
    check("customer report reflects the PREMIUM tier after upgrade (§14.2)",
          report.get("tier") == "PREMIUM", f"tier={report.get('tier')}")

    # 4. Re-check DECLINED (§14.1): request → admin refuses → no state change, customer told.
    declined_rc = customer.post(f"/verifications/{vid_id}/rechecks",
                                json={"reason": "The lawyer's citation list looks thin."}).json()["data"]
    decided = admin.post(f"/admin/rechecks/{declined_rc['id']}/decide",
                         json={"approve": False, "note": "Findings already re-verified twice."}).json()["data"]
    check("admin declines the re-check (PENDING → REJECTED, §14.1)", decided["status"] == "REJECTED")
    still = admin.get(f"/admin/review/{vid_id}").json()["data"]
    check("a declined re-check leaves the verification COMPLETED (§14.1)",
          still["status"] == "COMPLETED")
    types = {n["type"] for n in customer.get("/notifications").json()["data"]["items"]}
    check("customer got the RECHECK_DECISION notification (§12.2)", "RECHECK_DECISION" in types)

    # 5. Dispute UPHELD as PARTIAL_RECHECK (§14.3): scoped reopen → rework → v3 RECHECK report.
    disp = customer.post(f"/verifications/{vid_id}/disputes", json={
        "disputeType": "INACCURATE_FINDING", "description": "l" * 120, "targetRole": "LAWYER",
    }).json()["data"]
    check("second dispute opens (COMPLETED → DISPUTED, §14.3)", disp["status"] == "OPEN")
    resolved = admin.post(f"/admin/disputes/{disp['id']}/resolve", json={
        "outcome": "PARTIAL_RECHECK", "scopeRoles": ["LAWYER"],
        "note": "The legal opinion will be re-examined at no cost.",
    }).json()["data"]
    check("upheld dispute resolves to a scoped re-check (DISPUTED → IN_PROGRESS, §14.3)",
          resolved["status"] == "RESOLVED")
    reopened = admin.get(f"/admin/review/{vid_id}").json()["data"]
    l_state = next(t["state"] for t in reopened["tasks"] if t["role"] == "LAWYER")
    check("dispute reopened only the scoped LAWYER task (§14.3)",
          reopened["status"] == "IN_PROGRESS" and l_state == "IN_PROGRESS",
          f"verification={reopened['status']} lawyer={l_state}")

    lawyer.post(f"/agents/tasks/{l_task['id']}/submit",
                json={"payload": ROLE_PAYLOADS["LAWYER"]}).raise_for_status()
    admin.post(f"/admin/review/{vid_id}/tasks/LAWYER/approve", json={"quality": 97}).raise_for_status()
    v3 = admin.post(f"/admin/review/{vid_id}/release",
                    json={"reason": "Legal opinion re-examined and confirmed."}).json()["data"]
    check("dispute-driven rework releases the v3 report (§8.4/§14.3)",
          v3["status"] == "COMPLETED" and v3["report"]["reportVersion"] > v2_version,
          f"version={v3['report'] and v3['report']['reportVersion']}")
    check("the v3 report is marked as a RECHECK revision (§14)",
          v3["report"].get("revisionKind") == "RECHECK",
          f"kind={v3['report'].get('revisionKind')}")

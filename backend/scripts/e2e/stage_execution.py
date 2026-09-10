"""Stage 2 — admin assignment + agent task execution (S10 §6.3, S11 §12).

The first live coverage of the pipeline middle: for each STANDARD-tier role the admin
consults the ranked suggestions and assigns the seeded agent; the agent accepts, starts,
uploads content-hashed evidence (§4.5, §12.3), and submits the role form (§12.2). Once every
required task is SUBMITTED the derive owner promotes the verification to UNDER_REVIEW (§2.5).
"""
from __future__ import annotations

from .harness import MINIMAL_PNG, Ctx, check

# Minimal valid role forms (per-role required fields, task/validator.py §12.2).
ROLE_PAYLOADS = {
    "REGISTRY": {"registered_owner": "Chief A. Danladi", "title_search_result": "CLEAN",
                 "search_reference": "LAG/REG/2026/0042", "summary": "Registry search clear."},
    "FIELD": {"occupancy_status": "VACANT", "physical_condition": "Fenced, cleared plot.",
              "summary": "Site visit uneventful."},
    "SURVEYOR": {"area_sqm": 648, "beacon_status": "ALL_PRESENT",
                 "summary": "Beacons match the survey plan."},
    "LAWYER": {"legal_opinion": "Title chain is coherent.", "risk_level": "LOW",
               "recommendation": "PROCEED", "summary": "No encumbrances found."},
}


def run(ctx: Ctx) -> None:
    admin, vid_id = ctx.admin, ctx.vid_id
    # The fresh verification is STANDARD tier: drive exactly the roles its task set needs
    # (the seed's task map is keyed by them). The seeded agents also include LAWYER, but
    # that role only enters at the PREMIUM upgrade (stage_premium_release).
    roles = list(ctx.seed["tasks"].keys())

    for role in roles:
        agent_id = ctx.seed["agents"][role]

        # Admin: ranked suggestions include the seeded agent, then manual assignment (§6.3).
        suggested = admin.get(
            f"/admin/agents/suggested?verification_id={vid_id}&role={role}"
        ).json()["data"]
        check(f"suggested agents rank candidates for {role} (§16.1/§6.3)",
              len(suggested) >= 1 and "compositeScore" in suggested[0],
              f"suggested={len(suggested)}")
        r = admin.post(f"/admin/verifications/{vid_id}/tasks/{role}/assign",
                       json={"agentId": agent_id})
        check(f"admin assigned the {role} task to the seeded agent (§6.3)",
              r.status_code == 200, f"http {r.status_code}: {r.text[:200]}")

        # Agent: the assignment shows on their work surface (§12.1).
        agent = ctx.agent(role)
        tasks = agent.get("/agents/tasks").json()["data"]["items"]
        mine = next((t for t in tasks if t["verificationId"] == vid_id), None)
        check(f"{role} agent sees the assigned task on their dashboard (§12.1)",
              mine is not None and mine["state"] == "ASSIGNED",
              f"state={mine and mine['state']}")
        task_id = mine["id"]
        ctx.task_ids[role] = task_id

        # Accept → start → capture evidence → submit (§12.1, §12.2, §12.3).
        accepted = agent.post(f"/agents/tasks/{task_id}/accept").json()["data"]
        check(f"{role} agent accepted the task (§12.1)", accepted["state"] == "ACCEPTED")
        started = agent.post(f"/agents/tasks/{task_id}/start").json()["data"]
        check(f"{role} agent started the task (§12.2)", started["state"] == "IN_PROGRESS")

        evidence = agent.post(
            f"/agents/tasks/{task_id}/evidence",
            files={"file": (f"{role.lower()}-site.png", MINIMAL_PNG, "image/png")},
            data={"kind": "PHOTO", "gps_latitude": "6.4478", "gps_longitude": "3.4723"},
        ).json()["data"]
        check(f"{role} evidence upload is content-hashed at receipt (§4.5, §12.3)",
              bool(evidence.get("contentSha256")), f"sha256={evidence.get('contentSha256', '')[:12]}")
        listed = agent.get(f"/agents/tasks/{task_id}/evidence").json()["data"]
        check(f"{role} evidence is listed for the task (§12.3)",
              any(e["id"] == evidence["id"] for e in listed), f"count={len(listed)}")

        submitted = agent.post(f"/agents/tasks/{task_id}/submit",
                               json={"payload": ROLE_PAYLOADS[role]}).json()["data"]
        check(f"{role} agent submitted the role findings (§12.2)",
              submitted["state"] == "SUBMITTED", f"state={submitted['state']}")

    # Every required task SUBMITTED → derive owner promotes to UNDER_REVIEW (§2.5).
    status = admin.get(f"/admin/review/{vid_id}").json()["data"]["status"]
    check("all tasks submitted → verification derived to UNDER_REVIEW (§2.5)",
          status == "UNDER_REVIEW", f"status={status}")

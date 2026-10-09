"""Stage 2 — admin assignment + agent task execution (S10 §6.3, S11 §12).

The first live coverage of the pipeline middle: for each STANDARD-tier role the admin
consults the ranked suggestions and assigns the seeded agent; the agent accepts, starts,
uploads content-hashed evidence (§4.5, §12.3), and submits the role form (§12.2). Once every
required task is SUBMITTED the derive owner promotes the verification to UNDER_REVIEW (§2.5).
"""
from __future__ import annotations

from .harness import MINIMAL_PNG, Ctx, check, commission_by_role

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

    # The fixed per-role commission is admin-editable and round-trips (§20.1 / D97). The
    # original figure is restored so every later amount check reads the seeded defaults.
    commissions = commission_by_role(admin)
    check("every agent role has a fixed commission configured (§20.1)",
          set(commissions) == {"REGISTRY", "FIELD", "SURVEYOR", "LAWYER"}
          and all(v > 0 for v in commissions.values()), str(commissions))
    original = commissions["REGISTRY"]
    edited = admin.put("/admin/commission-rules/REGISTRY", json={"amountNgnKobo": original + 100}).json()["data"]
    restored = admin.put("/admin/commission-rules/REGISTRY", json={"amountNgnKobo": original}).json()["data"]
    check("admin edits a role's fixed commission, keyed by role alone (§20.1)",
          edited["amountNgnKobo"] == original + 100 and restored["amountNgnKobo"] == original,
          f"edited={edited.get('amountNgnKobo')} restored={restored.get('amountNgnKobo')}")
    refused = admin.put("/admin/commission-rules/REGISTRY", json={"amountNgnKobo": -1})
    check("a negative commission is refused (§20.1)", refused.status_code == 422,
          f"http {refused.status_code}")
    # BASIC pays only REGISTRY, so a REGISTRY commission of the whole BASIC price leaves no margin.
    basic_price = next(t for t in admin.get("/admin/pricing").json()["data"]["tiers"]
                       if t["tier"] == "BASIC")["priceNgnMinor"]
    greedy = admin.put("/admin/commission-rules/REGISTRY", json={"amountNgnKobo": basic_price})
    check("a commission that would eat a tier's minimum margin is refused (§20.1/D97)",
          greedy.status_code == 422 and "minimum margin" in greedy.json()["error"]["message"]
          and commission_by_role(admin)["REGISTRY"] == original,
          f"http {greedy.status_code}")

    for role in roles:
        agent_id = ctx.seed["agents"][role]["id"]

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
        check(f"{role} agent sees the job's fixed commission before accepting (§12.1/§20.1)",
              mine.get("commissionMinor") == commissions[role],
              f"shown={mine.get('commissionMinor')} rule={commissions[role]}")

        # Accept → start → capture evidence → submit (§12.1, §12.2, §12.3).
        accepted = agent.post(f"/agents/tasks/{task_id}/accept").json()["data"]
        check(f"{role} agent accepted the task (§12.1)", accepted["state"] == "ACCEPTED")
        if role == "REGISTRY":
            # The rate is locked at accept: a later rule change does not move what this task pays.
            admin.put(f"/admin/commission-rules/{role}", json={"amountNgnKobo": original + 100}).raise_for_status()
            card = agent.get("/agents/tasks").json()["data"]["items"]
            shown = next(t for t in card if t["id"] == task_id)["commissionMinor"]
            admin.put(f"/admin/commission-rules/{role}", json={"amountNgnKobo": original}).raise_for_status()
            check("an accepted task keeps the commission locked at accept (§12.1/§20.1)",
                  shown == commissions[role], f"shown={shown} locked={commissions[role]}")
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
        if role == roles[0]:
            _another_agent_cannot_touch(ctx, task_id, owner_role=role, other_role=roles[1])

        submitted = agent.post(f"/agents/tasks/{task_id}/submit",
                               json={"payload": ROLE_PAYLOADS[role]}).json()["data"]
        check(f"{role} agent submitted the role findings (§12.2)",
              submitted["state"] == "SUBMITTED", f"state={submitted['state']}")

    # Every required task SUBMITTED → derive owner promotes to UNDER_REVIEW (§2.5).
    status = admin.get(f"/admin/review/{vid_id}").json()["data"]["status"]
    check("all tasks submitted → verification derived to UNDER_REVIEW (§2.5)",
          status == "UNDER_REVIEW", f"status={status}")

    # The agent home summary counts the agent's own tasks server-side (§12).
    role = next(iter(ctx.task_ids))
    summary = ctx.agent(role).get("/agents/tasks/summary").json()["data"]
    check("the agent summary counts their submitted work (§12)",
          summary["submitted"] >= 1 and summary["assigned"] >= 0, f"summary={summary}")


def _another_agent_cannot_touch(ctx: Ctx, task_id: str, *, owner_role: str, other_role: str) -> None:
    """Every agent action on a task is checked against the database's owner, not the caller's
    claim: a second, fully approved agent reaches none of it — not the evidence's signed links,
    not the history, not a single state change."""
    other = ctx.agent(other_role)
    attempts = {
        "start": other.post(f"/agents/tasks/{task_id}/start"),
        "decline": other.post(f"/agents/tasks/{task_id}/decline", json={"reason": "not mine"}),
        "upload evidence": other.post(
            f"/agents/tasks/{task_id}/evidence",
            files={"file": ("intruder.png", MINIMAL_PNG, "image/png")}, data={"kind": "PHOTO"},
        ),
        "read evidence": other.get(f"/agents/tasks/{task_id}/evidence"),
        "read history": other.get(f"/agents/tasks/{task_id}/history"),
        "submit": other.post(f"/agents/tasks/{task_id}/submit", json={"payload": ROLE_PAYLOADS[owner_role]}),
    }
    reached = {name: r.status_code for name, r in attempts.items() if not 400 <= r.status_code < 500}
    check(f"another agent can't act on or read the {owner_role} task by its id (IDOR)",
          not reached, f"reached={reached}")
    owned = ctx.agent(owner_role).get("/agents/tasks").json()["data"]["items"]
    state = next(t["state"] for t in owned if t["id"] == task_id)
    check("the owner's task is untouched by those attempts", state == "IN_PROGRESS", f"state={state}")

"""Stage 3 — admin invitation & RBAC (S8 §4).

SUPER invites a new admin (the invite URL carries the raw token in-body — dev contract),
the invitee accepts and re-logs-in to pick up the ADMIN claims, then the RBAC boundaries
are asserted both ways: OPERATIONS holds APPROVE_AGENT but not INVITE_ADMIN (SUPER-only),
sub-role changes are SUPER-gated, revoked invitations die, and deactivation demotes to USER.
"""
from __future__ import annotations

from .harness import QA_PASSWORD, Ctx, check, login, signup_fresh_user


def run(ctx: Ctx) -> None:
    admin = ctx.admin  # SUPER

    # Invitee must exist with the invited email (accept matches on the caller's email).
    invitee, invitee_email = signup_fresh_user("qa-invitee", first_name="Ify", last_name="Invitee")

    invited = admin.post("/users/admins/invitations",
                         json={"email": invitee_email, "firstName": "Ify", "lastName": "Invitee",
                               "subRole": "OPERATIONS"}).json()["data"]
    invite_url = invited.get("inviteUrl", "")
    token = invite_url.rstrip("/").split("/")[-1]
    check("SUPER issues an admin invitation with an in-body invite URL (§4.1)", bool(token),
          f"url={invite_url}")

    preview = ctx.root.get(f"/users/admins/invitations/preview/{token}").json()["data"]
    check("unauthenticated preview resolves the invite (EXISTING_USER, §4.1)",
          preview["scenario"] == "EXISTING_USER" and preview["subRole"] == "OPERATIONS",
          f"scenario={preview['scenario']}")

    accepted = invitee.post("/users/admins/invitations/accept", json={"token": token}).json()["data"]
    check("invitee accepts → granted the OPERATIONS sub-role (§4.1)",
          accepted["subRole"] == "OPERATIONS")

    # The pre-accept JWT still says USER — a fresh login carries the ADMIN claims.
    ops_admin = login(invitee_email, QA_PASSWORD)
    r = ops_admin.get("/users/agents/applications")
    check("OPERATIONS admin can reach the agent-approval queue (APPROVE_AGENT, §4.2)",
          r.status_code == 200, f"http {r.status_code}")
    r = ops_admin.post("/users/admins/invitations", json={"email": "x@veriprops.io", "subRole": "FINANCE"})
    check("OPERATIONS cannot invite admins (INVITE_ADMIN is SUPER-only, §4.2)",
          r.status_code == 403, f"http {r.status_code}")

    team = admin.get("/users/admins/team").json()["data"]
    member = next((m for m in team["items"] if m.get("email") == invitee_email), None)
    check("team list shows the new admin (§4.3)", member is not None, f"team={len(team['items'])}")
    invitee_user_id = member["id"] if member else ""
    super_id = next((m["id"] for m in team["items"] if m.get("email") != invitee_email), "")

    r = ops_admin.post(f"/users/admins/team/{super_id}/sub-role", json={"subRole": "FINANCE"})
    check("non-SUPER cannot change sub-roles (§4.3 guard)", r.status_code == 403,
          f"http {r.status_code}")
    changed = admin.post(f"/users/admins/team/{invitee_user_id}/sub-role",
                         json={"subRole": "FINANCE"})
    check("SUPER changes the invitee's sub-role to FINANCE (§4.3)", changed.status_code == 200,
          f"http {changed.status_code}: {changed.text[:160]}")

    # Revocation kills a pending invitation before acceptance.
    revoke_email = f"never-{invitee_email}"
    second = admin.post("/users/admins/invitations",
                        json={"email": revoke_email, "subRole": "FINANCE"}).json()["data"]
    second_token = second["inviteUrl"].rstrip("/").split("/")[-1]
    invitations = admin.get("/users/admins/invitations").json()["data"]["items"]
    second_row = next(i for i in invitations if i["email"] == revoke_email)
    admin.post(f"/users/admins/invitations/{second_row['id']}/revoke").raise_for_status()
    revoked_preview = ctx.root.get(f"/users/admins/invitations/preview/{second_token}").json()["data"]
    check("revoked invitation previews as no longer PENDING (§4.1)",
          revoked_preview["status"] != "PENDING", f"status={revoked_preview['status']}")
    dead = invitee.post("/users/admins/invitations/accept", json={"token": second_token})
    check("a revoked invitation cannot be accepted (§4.1)", dead.status_code >= 400,
          f"http {dead.status_code}")

    # Deactivation demotes the admin back to a plain USER.
    admin.post(f"/users/admins/team/{invitee_user_id}/deactivate").raise_for_status()
    demoted = login(invitee_email, QA_PASSWORD)
    r = demoted.get("/users/agents/applications")
    check("deactivated admin is demoted to USER (admin surface now 403, §4.3)",
          r.status_code == 403, f"http {r.status_code}")

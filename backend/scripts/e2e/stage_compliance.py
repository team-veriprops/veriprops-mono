"""Stage 10 — audit & compliance maturity (S23 §19, §4.11 NDPA erasure).

The audit-pack export runs against the FRESH verification, whose trail was written by the
real services this run drove (state transitions, evidence hashes, consent snapshots) — a
stronger §19.3 exit-criterion assertion than the seed's fabricated rows. The erasure flow
uses the seed's disposable ``qa-erasable`` account so scrubbing never disturbs earlier checks.
"""
from __future__ import annotations

from .harness import QA_PASSWORD, Ctx, check, login, login_status


def run(ctx: Ctx) -> None:
    admin, customer, vid_id = ctx.admin, ctx.customer, ctx.vid_id
    erasable = ctx.seed["erasable"]

    # ── §19.3 exit criterion: a legally defensible audit pack for the fresh VID ──
    export = admin.get(f"/admin/audit/verifications/{vid_id}/export")
    body = export.text
    check("audit-pack export returns CSV (§19.3)",
          export.status_code == 200 and "text/csv" in export.headers.get("content-type", ""),
          export.headers.get("content-type", ""))
    check("audit pack carries the live-run transition backbone (§19.3)",
          "record_type" in body and "TRANSITION" in body and "VERIFICATION_STATE_CHANGED" in body)
    check("audit pack carries the evidence content hashes (§19.3, §4.5)",
          "EVIDENCE" in body, f"bytes={len(body)}")

    # ── Agent task-history read model (R19.3) — the fresh task's real transitions ──
    role, task_id = next(iter(ctx.task_ids.items()))
    hist = ctx.agent(role).get(f"/agents/tasks/{task_id}/history").json()["data"]
    check("agent sees their task's transition history (R19.3)",
          hist.get("total", 0) >= 1, f"total={hist.get('total')}")

    # ── Versioned consent download (R19.4) — the fresh customer has real consent rows ──
    dl = customer.get("/users/auth/consents/history/download")
    check("consent history downloads as CSV (R19.4)",
          dl.status_code == 200 and dl.text.splitlines()[0].startswith("document_type"))
    check("consent CSV carries the signup consents (R19.4)",
          "PLATFORM_TERMS" in dl.text and "PRIVACY_POLICY" in dl.text)

    # ── Compliance config keys are seeded + surfaced (§19.1) ──────
    cfg = admin.get("/admin/config/settings").json()["data"]
    keys = {c["key"] for c in cfg}
    check("compliance config keys seeded (§19.1)",
          "pii_retention_days" in keys and "erasure_request_review_sla_days" in keys)

    # ── NDPA erasure — admin REJECT branch first (terminal but non-destructive, §19.1) ──
    rejected_req = customer.post("/users/me/erasure-requests",
                                 json={"reason": "Second thoughts about my data"}).json()["data"]
    check("fresh customer's erasure request opens as PENDING (§N.5)",
          rejected_req["status"] == "PENDING")
    rej = admin.post(f"/admin/erasure-requests/{rejected_req['id']}/reject",
                     json={"note": "Active verification history — retention basis applies."}).json()["data"]
    check("admin rejects the erasure request (PENDING → REJECTED, §4.11)",
          rej["status"] == "REJECTED")
    check("a rejected erasure never scrubs — the subject still logs in (§4.11)",
          login_status(ctx.customer_email, QA_PASSWORD) == 200)

    # ── NDPA data-erasure workflow — approve → execute (§18.1, §19.1, §4.11) ──────────
    erasable_c = login(erasable["email"], erasable["password"])
    req = erasable_c.post("/users/me/erasure-requests", json={"reason": "Please erase my data"}).json()["data"]
    check("self-service erasure request opens as PENDING (§N.5)",
          req["status"] == "PENDING" and req.get("slaDueAt"))

    dup = erasable_c.post("/users/me/erasure-requests", json={"reason": "again"})
    check("a second in-flight request is blocked", dup.status_code >= 400, f"status={dup.status_code}")

    forbidden = customer.get("/admin/erasure-requests")
    check("non-compliance user cannot see the admin erasure queue (MANAGE_COMPLIANCE)",
          forbidden.status_code == 403, f"status={forbidden.status_code}")

    pending = admin.get("/admin/erasure-requests", params={"status": "PENDING"}).json()["data"]
    req_id = pending["items"][0]["id"]
    check("admin erasure queue lists the pending request (§18.1)",
          any(i["subjectUserId"] == erasable["id"] for i in pending["items"]))

    admin.post(f"/admin/erasure-requests/{req_id}/approve").raise_for_status()
    executed = admin.post(f"/admin/erasure-requests/{req_id}/execute").json()["data"]
    check("admin executes the erasure → EXECUTED (§4.11)", executed["status"] == "EXECUTED")

    # The erased account can no longer authenticate (identity + credentials pseudonymised).
    check("erased account can no longer log in (PII scrubbed)",
          login_status(erasable["email"], erasable["password"]) != 200)

    # The erasure itself is recorded, and the pseudonymised surfaces include the audit actor (§4.11).
    actions = admin.get(
        "/admin/audit/actions", params={"action_types": ["DATA_ERASURE_EXECUTED"]}
    ).json()["data"]
    executed_row = next((a for a in actions["items"] if a["action"] == "DATA_ERASURE_EXECUTED"), None)
    check("erasure execution is itself audited (§4.11)", executed_row is not None)
    surfaces = (executed_row or {}).get("details", {}).get("surfaces", [])
    check("audit actor identity is among the pseudonymised surfaces (§4.11)",
          "users" in surfaces and "audit_logs" in surfaces, f"surfaces={surfaces}")

"""Live drive-through of the S23 (§19 audit & compliance maturity) surfaces.

Runs against a real backend on :8000 on top of the deterministic dev seed. Exercises the
§19.3 exit criterion (admin exports a legally defensible audit pack for a VID), the customer
activity feed + agent task-history read models, versioned consent download, the new compliance
config keys, and the full NDPA data-erasure workflow — self-service request → admin approve →
execute (irreversible PII pseudonymisation, §4.11). Prints PASS/FAIL per step.

How to run (non-prod only): start the backend (local env, ENABLE_OUT_MESSAGING=False), then:
    set PYTHONIOENCODING=utf-8 && python scripts/e2e_s23.py
"""
from __future__ import annotations

import sys

import httpx

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE = "http://localhost:8000/api"
_failures = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        _failures.append(name)


def login(email: str, password: str) -> httpx.Client:
    c = httpx.Client(base_url=BASE, timeout=30.0)
    c.post("/users/auth/sessions", json={"email": email, "password": password}).raise_for_status()
    jar = {k: v for k, v in c.cookies.items()}
    if jar:
        c.headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in jar.items())
    csrf = jar.get("__Host-access_csrf_token")
    if csrf:
        c.headers["X-CSRF-Token"] = csrf
    return c


def _login_status(email: str, password: str) -> int:
    return httpx.Client(base_url=BASE, timeout=30.0).post(
        "/users/auth/sessions", json={"email": email, "password": password}
    ).status_code


def main() -> int:
    root = httpx.Client(base_url=BASE, timeout=30.0)
    root.post("/dev/reset").raise_for_status()
    seed = root.post("/dev/seed").json()["data"]
    cust, admin, erasable = seed["customer"], seed["admin"], seed["erasable"]
    vid = seed["verification"]["id"]
    role, task_id = next(iter(seed["tasks"].items()))

    customer = login(cust["email"], cust["password"])
    admin_c = login(admin["email"], admin["password"])
    agent = login(f"qa-agent-{role.lower()}@veriprops.io", "Test1234!")

    # ── §19.3 exit criterion: admin exports a legally defensible audit pack for a VID ──
    export = admin_c.get(f"/admin/audit/verifications/{vid}/export")
    body = export.text
    check("audit-pack export returns CSV (§19.3)",
          export.status_code == 200 and "text/csv" in export.headers.get("content-type", ""),
          export.headers.get("content-type", ""))
    check("audit pack carries the transition backbone (§19.3)",
          "record_type" in body and "TRANSITION" in body and "VERIFICATION_STATE_CHANGED" in body)

    # ── Customer activity feed (R19.2) — PII-safe (no actorId) ──────────
    activity = customer.get(f"/verifications/{vid}/activity").json()["data"]
    check("customer activity feed lists transitions (R19.2)", activity["total"] >= 1,
          f"total={activity['total']}")
    check("activity events are PII-safe (no actorId leaked, §9.5/§19)",
          all("actorId" not in item and "actor_id" not in item for item in activity["items"]))

    # ── Agent task-history read model (R19.3) ───────────────────────────
    hist = agent.get(f"/agents/tasks/{task_id}/history").json()["data"]
    check("agent sees their task's transition history (R19.3)", "items" in hist,
          f"total={hist.get('total')}")

    # ── Versioned consent download (R19.4) ──────────────────────────────
    dl = customer.get("/users/auth/consents/history/download")
    check("consent history downloads as CSV (R19.4)",
          dl.status_code == 200 and dl.text.splitlines()[0].startswith("document_type"))

    # ── Compliance config keys are seeded + surfaced (§19.1) ────────────
    cfg = admin_c.get("/admin/config/settings").json()["data"]
    keys = {c["key"] for c in cfg}
    check("compliance config keys seeded (§19.1)",
          "pii_retention_days" in keys and "erasure_request_review_sla_days" in keys)

    # ── NDPA data-erasure workflow (§18.1, §19.1, §4.11) ────────────────
    erasable_c = login(erasable["email"], erasable["password"])
    req = erasable_c.post("/users/me/erasure-requests", json={"reason": "Please erase my data"}).json()["data"]
    check("self-service erasure request opens as PENDING (§N.5)",
          req["status"] == "PENDING" and req.get("slaDueAt"))

    dup = erasable_c.post("/users/me/erasure-requests", json={"reason": "again"})
    check("a second in-flight request is blocked", dup.status_code >= 400, f"status={dup.status_code}")

    forbidden = customer.get("/admin/erasure-requests")
    check("non-compliance user cannot see the admin erasure queue (MANAGE_COMPLIANCE)",
          forbidden.status_code == 403, f"status={forbidden.status_code}")

    pending = admin_c.get("/admin/erasure-requests", params={"status": "PENDING"}).json()["data"]
    req_id = pending["items"][0]["id"]
    check("admin erasure queue lists the pending request (§18.1)",
          any(i["subjectUserId"] == erasable["id"] for i in pending["items"]))

    admin_c.post(f"/admin/erasure-requests/{req_id}/approve").raise_for_status()
    executed = admin_c.post(f"/admin/erasure-requests/{req_id}/execute").json()["data"]
    check("admin executes the erasure → EXECUTED (§4.11)", executed["status"] == "EXECUTED")

    # The erased account can no longer authenticate (identity + credentials pseudonymised).
    check("erased account can no longer log in (PII scrubbed)",
          _login_status(erasable["email"], erasable["password"]) != 200)

    # The erasure itself is recorded, and the pseudonymised surfaces include the audit actor (§4.11).
    actions = admin_c.get(
        "/admin/audit/actions", params={"action_types": ["DATA_ERASURE_EXECUTED"]}
    ).json()["data"]
    executed_row = next((a for a in actions["items"] if a["action"] == "DATA_ERASURE_EXECUTED"), None)
    check("erasure execution is itself audited (§4.11)", executed_row is not None)
    surfaces = (executed_row or {}).get("details", {}).get("surfaces", [])
    check("audit actor identity is among the pseudonymised surfaces (§4.11)",
          "users" in surfaces and "audit_logs" in surfaces, f"surfaces={surfaces}")

    print()
    if _failures:
        print(f"{len(_failures)} FAILED: {_failures}")
        return 1
    print("ALL S23 CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())

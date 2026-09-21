"""Stage 2 — agent onboarding & KYC (S7 §3).

The live application funnel the seed shortcuts (seeded agents are injected pre-APPROVED):
a fresh user saves + resumes the wizard draft, submits the application (credentials ride in
the payload; KYC runs synchronously against the deterministic stub), and the admin drives
both review outcomes — approve (§3.2, flips credentials VERIFIED) and reject with a reason.
Also asserts the §3.3a credential requirement (SURVEYOR without a licence is refused).
"""
from __future__ import annotations

from .harness import Ctx, check, consent_version_for, signup_fresh_user

# Deterministic stub KYC sentinels (integrations/kyc/stub): anything else verifies.
_KYC_FAILING_BVN = "00000000000"


def run(ctx: Ctx) -> None:
    admin = ctx.admin

    # ── Applicant #1: SURVEYOR (credentialed role) → APPROVED ─────
    applicant, applicant_email = signup_fresh_user("qa-applicant", first_name="Bisi", last_name="Applicant")

    saved = applicant.put("/users/agents/application/draft",
                          json={"step": 2, "payload": {"roles": ["SURVEYOR"]}}).json()["data"]
    check("application wizard draft saves (§3.1)", saved["step"] == 2)
    resumed = applicant.get("/users/agents/application/draft").json()["data"]
    check("application wizard draft resumes (§3.1)",
          resumed and resumed["payload"].get("roles") == ["SURVEYOR"])

    # §3.3a: a credentialed role without its licence is refused outright.
    bad = applicant.post("/users/agents/application", json={
        "roles": ["SURVEYOR"], "kyc": {"method": "BVN", "bvn": "22233344455"},
        "truthfulnessConfirmed": True, "agentTermsVersion": consent_version_for("AGENT_TERMS"),
    })
    check("SURVEYOR application without a licence is refused (§3.3a)",
          bad.status_code >= 400, f"http {bad.status_code}")

    submitted = applicant.post("/users/agents/application", json={
        "roles": ["SURVEYOR"],
        "credentials": [{"role": "SURVEYOR", "credentialType": "SURVEYOR_LICENCE",
                         "licenceNumber": "SUR-2026-0099", "expiryDate": "2027-12-31"}],
        "coverage": [{"state": "lagos", "lga": "eti-osa"}],
        "kyc": {"method": "BVN", "bvn": "22233344455"},  # non-sentinel → stub VERIFIED
        "bio": "Licensed surveyor, 6 years in Lagos.", "yearsExperience": 6,
        "truthfulnessConfirmed": True, "agentTermsVersion": consent_version_for("AGENT_TERMS"),
    }).json()["data"]
    check("agent application submitted → PENDING (§3.1)", submitted["status"] == "PENDING")

    queue = admin.get("/users/agents/applications", params={"status": "PENDING"}).json()["data"]["items"]
    mine = next((a for a in queue if a.get("applicantName") == "Bisi Applicant"), None)
    check("application appears in the admin review queue (§3.2)", mine is not None,
          f"queue={len(queue)}")
    profile_id = mine["id"]

    detail = admin.get(f"/users/agents/applications/{profile_id}").json()["data"]
    check("admin detail carries the applicant email + stub KYC outcome (§3.1)",
          detail.get("applicantEmail") == applicant_email and detail.get("kyc") is not None,
          f"kyc={detail.get('kyc')}")

    approved = admin.post(f"/users/agents/applications/{profile_id}/approve",
                          json={"approvedRoles": ["SURVEYOR"]}).json()["data"]
    check("admin approves the application (PENDING → APPROVED, §3.2)",
          approved["status"] == "APPROVED")
    status = applicant.get("/users/agents/application").json()["data"]
    check("applicant sees APPROVED with the SURVEYOR role (§3.2)",
          status["status"] == "APPROVED" and "SURVEYOR" in (status.get("approvedRoles") or []),
          f"status={status.get('status')} roles={status.get('approvedRoles')}")

    # ── Applicant #2: REGISTRY with a failing stub KYC → admin REJECTS ─────
    reject_c, _reject_email = signup_fresh_user("qa-applicant2", first_name="Tunde", last_name="Applicant")
    second = reject_c.post("/users/agents/application", json={
        "roles": ["REGISTRY"],
        "coverage": [{"state": "lagos", "lga": "ikeja"}],
        "kyc": {"method": "BVN", "bvn": _KYC_FAILING_BVN},  # stub sentinel → FAILED
        "truthfulnessConfirmed": True, "agentTermsVersion": consent_version_for("AGENT_TERMS"),
    }).json()["data"]
    check("failed stub KYC still lodges a PENDING application for review (§3.1)",
          second["status"] == "PENDING")

    queue2 = admin.get("/users/agents/applications", params={"status": "PENDING"}).json()["data"]["items"]
    second_id = next(a["id"] for a in queue2 if a.get("applicantName") == "Tunde Applicant")
    rejected = admin.post(f"/users/agents/applications/{second_id}/reject",
                          json={"reason": "KYC verification failed."}).json()["data"]
    check("admin rejects the application with a reason (PENDING → REJECTED, §3.2)",
          rejected["status"] == "REJECTED")
    status2 = reject_c.get("/users/agents/application").json()["data"]
    check("rejected applicant sees the rejection reason (§3.2)",
          status2["status"] == "REJECTED" and bool(status2.get("rejectionReason")),
          f"reason={status2.get('rejectionReason')}")

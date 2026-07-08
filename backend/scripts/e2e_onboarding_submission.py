"""Live drive-through of the customer acquisition + fresh-verification happy path (Phases 2 & 5).

Covers the acquisition funnel that the seed-based drive-throughs skip (the seed injects a
ready-made UNDER_REVIEW verification): email OTP → consent → signup → draft → quote → submit
→ pay (stub) → assignment. Complements e2e_drive_through.py (which starts already UNDER_REVIEW).

Run with phone verification ON so the full happy path reaches payment. (With
PHONE_VERIFICATION_ENABLED=false the customer is collected-but-unverified at signup and the
Phase-5 payment gate "Verify your phone number before paying" has no wired satisfy-path —
a known gap; see mark_phone_verified in user/service.py, currently uncalled.)

How to run (non-prod only — uses /dev/reset):
    set appodus_active_env=local && set ENABLE_OUT_MESSAGING=False && set PHONE_VERIFICATION_ENABLED=True && python veriprops.py
    set PYTHONIOENCODING=utf-8 && python scripts/e2e_onboarding_submission.py
"""
from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone

import httpx

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE = "http://localhost:8000/api"
TEST_OTP = "654123"  # deterministic OTP (OTP_MODE=deterministic in non-prod)
CONSENT_VERSION = "1.0.0"
_failures = []


def check(name: str, ok: bool, detail: str = "") -> None:
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        _failures.append(name)


def _pin_session_cookies(client: httpx.Client) -> None:
    """__Host- Secure cookies aren't resent by httpx over plain http — pin them onto an
    explicit Cookie header + the double-submit CSRF header for the run (mirrors login)."""
    jar = {k: v for k, v in client.cookies.items()}
    if jar:
        client.headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in jar.items())
    csrf = jar.get("__Host-access_csrf_token")
    if csrf:
        client.headers["X-CSRF-Token"] = csrf


def main() -> int:
    root = httpx.Client(base_url=BASE, timeout=30.0)
    root.post("/dev/reset").raise_for_status()
    check("dev reset ran (clean slate for a fresh signup)", True)

    email = f"qa-fresh-{uuid.uuid4().hex[:8]}@veriprops.io"
    now = datetime.now(timezone.utc).isoformat()

    # 1. Email OTP send + verify (signup requires a recent email OTP marker, §2).
    r = root.post("/users/auth/otp/send", json={"channel": "EMAIL", "email": email, "fullname": "Ada QA"})
    check("email OTP send accepted (§2)", r.status_code == 200, f"http {r.status_code}")
    r = root.post("/users/auth/otp/verify", json={"channel": "EMAIL", "email": email, "code": TEST_OTP})
    check("email OTP verified with deterministic code (§2)", r.status_code == 200
          and r.json()["data"].get("verified") is True, f"http {r.status_code}")

    # 1b. Phone OTP send + verify (so phone_verified=True carries into signup, satisfying the
    # Phase-5 payment gate). Requires PHONE_VERIFICATION_ENABLED=true on the server.
    dial_code, phone = "+234", "8030000001"
    r = root.post("/users/auth/otp/send", json={"channel": "PHONE", "country_code": "NG",
                                                "dial_code": dial_code, "phone": phone})
    check("phone OTP send accepted (§2)", r.status_code == 200, f"http {r.status_code}")
    r = root.post("/users/auth/otp/verify", json={"channel": "PHONE", "country_code": "NG",
                                                  "dial_code": dial_code, "phone": phone, "code": TEST_OTP})
    check("phone OTP verified with deterministic code (§2)", r.status_code == 200
          and r.json()["data"].get("verified") is True, f"http {r.status_code}")

    # 2. Signup with the two required consents → issues the session (Phase 2).
    client = httpx.Client(base_url=BASE, timeout=30.0)
    signup_body = {
        "first_name": "Ada", "last_name": "QA", "email": email, "password": "Test1234!",
        "country_code": "NG", "dial_code": "+234", "phone": "8030000001",
        "country_of_residence": "NG", "timezone": "Africa/Lagos", "preferred_currency": "NGN",
        "consents": [
            {"document_type": "PLATFORM_TERMS", "consent_version": CONSENT_VERSION, "accepted_at": now},
            {"document_type": "PRIVACY_POLICY", "consent_version": CONSENT_VERSION, "accepted_at": now},
        ],
    }
    r = client.post("/users/auth/signup", json=signup_body)
    check("signup created the account + session (Phase 2)", r.status_code in (200, 201), f"http {r.status_code}: {r.text[:200]}")
    _pin_session_cookies(client)

    # 3. Create a fresh verification draft → DRAFT with a VID (§5.1).
    r = client.post("/verifications/draft")
    check("verification draft created (§5.1)", r.status_code == 200, f"http {r.status_code}: {r.text[:200]}")
    draft = r.json()["data"]
    vid_id = draft["id"]
    check("draft starts in DRAFT with a VID (§2.1/§4.10)",
          draft.get("status") == "DRAFT" and str(draft.get("vid", "")).startswith("VP-"),
          f"status={draft.get('status')} vid={draft.get('vid')}")

    # 4. Quote the STANDARD tier (§5.2).
    r = client.get("/verifications/quote", params={"tier": "STANDARD", "currency": "NGN"})
    check("STANDARD tier quote returned a price (§5.2)", r.status_code == 200
          and r.json()["data"]["netPriceNgnMinor"] > 0, f"http {r.status_code}: {r.text[:160]}")

    # 5. Submit property + tier + consent → SUBMITTED, price locked (§5.6).
    submit_body = {
        "property": {
            "property_type": "LAND", "address": "3 Freedom Way, Lekki Phase 1",
            "state": "Lagos", "lga": "Eti-Osa", "landmark": "Opposite the roundabout",
        },
        "tier": "STANDARD", "currency": "NGN",
        "consent": {"consent_version": CONSENT_VERSION},
    }
    r = client.post(f"/verifications/{vid_id}/submit", json=submit_body)
    check("submit finalised the verification (§5.6)", r.status_code == 200, f"http {r.status_code}: {r.text[:220]}")
    submitted = r.json()["data"]
    check("submitted verification has a locked price (§4.4)",
          bool(submitted.get("priceLockedMinor") or submitted.get("price_locked_minor")),
          f"status={submitted.get('status')}")

    # 6. Initiate payment → tx_ref, then deterministically confirm it (§5.4, stub gateway).
    r = client.post(f"/payments/initiate/{vid_id}", json={"method": "CARD"})
    check("payment initiated (§5.4)", r.status_code == 200, f"http {r.status_code}: {r.text[:200]}")
    payment = r.json()["data"]
    tx_ref = payment.get("txRef") or payment.get("tx_ref")
    check("payment carries a tx_ref for the gateway (§4.6)", bool(tx_ref), f"payment={payment}")

    r = client.post("/payments/stub/confirm", json={"tx_ref": tx_ref, "succeeded": True})
    check("stub gateway confirmed the payment → PAID (§4.6)", r.status_code == 200
          and r.json()["data"].get("processed") is True, f"http {r.status_code}: {r.text[:160]}")

    # 7. Payment moves the verification out of the customer's hands into the work pipeline.
    r = client.get(f"/verifications/{vid_id}")
    check("paid verification progressed past DRAFT/SUBMITTED into the pipeline (§5.6→§6)",
          r.status_code == 200 and r.json()["data"]["status"] not in ("DRAFT", "SUBMITTED"),
          f"status={r.json()['data'].get('status')}")

    print("\n" + ("ALL PASSED" if not _failures else f"FAILURES: {_failures}"))
    return 1 if _failures else 0


if __name__ == "__main__":
    sys.exit(main())

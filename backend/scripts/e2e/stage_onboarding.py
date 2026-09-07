"""Stage 1 — customer acquisition + fresh-verification submission (Phases 2 & 5, §17.1).

Covers the funnel the seed shortcuts: email OTP → consent → signup (with the seeded
customer's referral code, §17.1/D34) → draft (Idempotency-Key + replay) → quote with the
growth discount breakdown → re-lock guard → submit (price lock) → Phase-5 phone verify →
stub payment → PAID. Leaves ``ctx.customer``/``ctx.vid_id``/``ctx.vid`` for later stages.

Runs against the default config (PHONE_VERIFICATION_ENABLED=false): the number is collected
but left unverified at signup, then verified at the Phase-5 payment step via the authenticated
POST /users/auth/phone/otp/send + /users/auth/phone/verify endpoints (satisfying the payment
"Verify your phone number before paying" gate).
"""
from __future__ import annotations

from .harness import TEST_OTP, Ctx, check, consent_version_for, idem_key, signup_fresh_user


def run(ctx: Ctx) -> None:
    # 0. The seeded customer is the referrer: capture their referral link (§17.1).
    referral = ctx.seed_customer.get("/referrals/me").json()["data"]
    ctx.referral_code = referral.get("code", "")
    check("referral link is issued for the customer (§17.1)", bool(ctx.referral_code),
          f"code={ctx.referral_code}")
    check("referral share path targets signup with the ref code",
          ctx.referral_code in referral.get("sharePath", ""))

    # 1–2. Email OTP → consent-gated signup, carrying the referral code (§2, §17.1/D34).
    fresh, email = signup_fresh_user("qa-fresh", referral_code=ctx.referral_code or None)
    ctx.customer = fresh
    ctx.customer_email = email

    # 2b. Before the customer has started any verification: nothing resumable, and the
    # session flag that gates the first-login auto-launch of the wizard is still false.
    pre_resumable = fresh.get("/verifications/draft/resumable").json()["data"]
    check("no resumable draft before the customer has started one (§ auto-resume gate)",
          pre_resumable is None, f"resumable={pre_resumable}")
    pre_session = fresh.get("/users/auth/sessions/current").json()["data"]
    check("hasStartedVerification is false before any draft exists (§ first-login auto-launch)",
          pre_session["user"]["hasStartedVerification"] is False)

    # 3. Create a fresh verification draft → DRAFT with a VID (§5.1). The wizard always sends
    # an Idempotency-Key (§4.6), so drive it here — a regression that broke the key path once
    # made this endpoint 404 and silently disabled the whole wizard.
    key = idem_key()
    r = fresh.post("/verifications/draft", headers={"Idempotency-Key": key})
    check("verification draft created with Idempotency-Key (§5.1/§4.6)", r.status_code == 200,
          f"http {r.status_code}: {r.text[:200]}")
    draft = r.json()["data"]
    ctx.vid_id = draft["id"]
    ctx.vid = draft.get("vid", "")
    check("draft starts in DRAFT with a VID (§2.1/§4.10)",
          draft.get("status") == "DRAFT" and str(draft.get("vid", "")).startswith("VP-"),
          f"status={draft.get('status')} vid={draft.get('vid')}")
    r = fresh.post("/verifications/draft", headers={"Idempotency-Key": key})
    check("replaying the Idempotency-Key returns the same draft, not a duplicate (§4.6)",
          r.status_code == 200 and r.json()["data"]["id"] == ctx.vid_id, f"http {r.status_code}")

    # 3a. The very first draft flips the customer's session flag (§ first-login auto-launch
    # of the wizard never re-fires); a still-blank draft (draft_step 0) isn't resumable yet
    # (§ new-verification staging is dirty-gated) — only a dirtied one blocks a second start.
    post_create_session = fresh.get("/users/auth/sessions/current").json()["data"]
    check("hasStartedVerification flips true once a draft exists (§ first-login auto-launch)",
          post_create_session["user"]["hasStartedVerification"] is True)
    blank_resumable = fresh.get("/verifications/draft/resumable").json()["data"]
    check("a still-blank draft is not resumable yet (§ dirty-gated staging)",
          blank_resumable is None, f"resumable={blank_resumable}")

    # 3b. Re-lock guard on the not-yet-priced draft (§17.1) — no silent re-pricing.
    relock = fresh.post(f"/verifications/{ctx.vid_id}/refresh-lock").json()["data"]
    check("re-lock on a not-yet-priced draft reports no price change (§17.1)",
          relock["priceChanged"] is False)

    # 4. Quote the STANDARD tier with the growth discount breakdown (§5.2, §17.1). The fresh
    # customer has never paid, so the first-time discount is live here.
    quote = fresh.get("/verifications/quote", params={"tier": "STANDARD", "currency": "NGN"}).json()["data"]
    check("STANDARD tier quote returned a price (§5.2)", quote["netPriceNgnMinor"] > 0,
          f"net={quote['netPriceNgnMinor']}")
    check("quote carries the growth discount breakdown (§17.1)",
          "netPriceNgnMinor" in quote and "firstTimeDiscountMinor" in quote,
          f"first_time={quote.get('firstTimeDiscountMinor')}")
    check("quote net = price − total discount (reconciles)",
          quote["netPriceNgnMinor"] == quote["priceNgnMinor"] - quote["totalDiscountMinor"])

    # 5. Submit property + tier + consent → SUBMITTED, price locked (§5.6, §4.4).
    r = fresh.post(f"/verifications/{ctx.vid_id}/submit", json={
        "property": {
            "property_type": "LAND", "address": "3 Freedom Way, Lekki Phase 1",
            "state": "Lagos", "lga": "Eti-Osa", "landmark": "Opposite the roundabout",
        },
        "tier": "STANDARD", "currency": "NGN",
        "consent": {"consent_version": consent_version_for("VERIFICATION_TERMS")},
    })
    check("submit finalised the verification (§5.6)", r.status_code == 200,
          f"http {r.status_code}: {r.text[:220]}")
    submitted = r.json()["data"]
    ctx.vid = submitted.get("vid") or ctx.vid
    check("submitted verification has a locked price (§4.4)",
          bool(submitted.get("priceLockedMinor")), f"status={submitted.get('status')}")

    # 5a. Now dirtied+unpaid, this verification is resumable — and starting a fresh
    # draft with a brand-new Idempotency-Key silently resumes it instead of creating a
    # second one (§ can't start a new verification until the existing one is paid for).
    resumable = fresh.get("/verifications/draft/resumable").json()["data"]
    check("a submitted, still-unpaid verification is resumable (§ can't start a second)",
          resumable is not None and resumable["id"] == ctx.vid_id, f"resumable={resumable}")
    r = fresh.post("/verifications/draft", headers={"Idempotency-Key": idem_key()})
    check("starting a new verification while one is unpaid silently resumes the existing one",
          r.status_code == 200 and r.json()["data"]["id"] == ctx.vid_id,
          f"http {r.status_code}: {r.text[:200]}")

    # 5b. Phase-5 phone verification: the number was collected-but-unverified at signup
    # (PHONE_VERIFICATION_ENABLED=false), so verify it now to satisfy the payment gate (§5).
    r = fresh.post("/users/auth/phone/otp/send")
    check("Phase-5 phone OTP send (authenticated) accepted (§5)", r.status_code == 200,
          f"http {r.status_code}: {r.text[:160]}")
    r = fresh.post("/users/auth/phone/verify", json={"code": TEST_OTP})
    check("Phase-5 phone verify flips phone_verified (§5, fixes the payment-gate gap)",
          r.status_code == 200 and r.json()["data"].get("verified") is True,
          f"http {r.status_code}: {r.text[:160]}")

    # 6. Initiate payment → tx_ref, then deterministically confirm it (§5.4, stub gateway).
    r = fresh.post(f"/payments/initiate/{ctx.vid_id}", json={"method": "CARD"})
    check("payment initiated (§5.4)", r.status_code == 200, f"http {r.status_code}: {r.text[:200]}")
    payment = r.json()["data"]
    tx_ref = payment.get("txRef")
    check("payment carries a tx_ref for the gateway (§4.6)", bool(tx_ref), f"payment={payment}")
    r = fresh.post("/payments/stub/confirm", json={"tx_ref": tx_ref, "succeeded": True})
    check("stub gateway confirmed the payment → PAID (§4.6)", r.status_code == 200
          and r.json()["data"].get("processed") is True, f"http {r.status_code}: {r.text[:160]}")

    # 7. Payment moves the verification out of the customer's hands into the work pipeline.
    status = fresh.get(f"/verifications/{ctx.vid_id}").json()["data"]["status"]
    check("paid verification progressed past DRAFT/SUBMITTED into the pipeline (§5.6→§6)",
          status not in ("DRAFT", "SUBMITTED"), f"status={status}")

    # 7a. Paid — no longer resumable, so the customer can freely start a new verification.
    paid_resumable = fresh.get("/verifications/draft/resumable").json()["data"]
    check("a paid verification is no longer resumable (§ can't start a second)",
          paid_resumable is None, f"resumable={paid_resumable}")

    # 8. The invitee's first payment records a PENDING referral credit for the referrer
    # (§17.1, D35) — clearable this run because the prologue zeroed the chargeback window.
    referral_after = ctx.seed_customer.get("/referrals/me").json()["data"]
    check("invitee's first payment earned the referrer a PENDING credit (§17.1, D35)",
          referral_after["pendingCreditMinor"] > 0,
          f"pending={referral_after['pendingCreditMinor']}")

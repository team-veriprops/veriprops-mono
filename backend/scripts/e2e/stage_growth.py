"""Stage 8 — growth & conversion (S21 §17.1, D34/D35).

The referral chain is real end-to-end in this run: the fresh customer signed up with the
seeded customer's code (stage 1) and made their first payment, which recorded a PENDING
credit (asserted there). With the chargeback window zeroed in the prologue, the sweep now
clears it into the referrer's spendable balance and fires REFERRAL_CREDIT_EARNED.
"""
from __future__ import annotations

from .harness import Ctx, check, consent_version_for


def run(ctx: Ctx) -> None:
    admin, referrer = ctx.admin, ctx.seed_customer

    # Two-stage clearance (D35): the sweep moves the PENDING credit to CLEARED.
    swept = admin.post("/admin/verifications/sweeps/referral-credits").json()["data"]
    check("referral-credit sweep clears the earned credit (§17.1, D35)",
          swept.get("cleared", 0) >= 1, f"cleared={swept.get('cleared')}")

    summary = referrer.get("/referrals/me").json()["data"]
    check("cleared credit lands in the referrer's spendable balance (§17.1)",
          summary["availableCreditMinor"] > 0 and summary["lifetimeCreditMinor"] > 0,
          f"available={summary['availableCreditMinor']} lifetime={summary['lifetimeCreditMinor']}")
    types = {n["type"] for n in referrer.get("/notifications").json()["data"]["items"]}
    check("referrer got the REFERRAL_CREDIT_EARNED notification (§12.2)",
          "REFERRAL_CREDIT_EARNED" in types, str(types))

    # ── Credit SPEND (§17.1): the referrer's cleared balance auto-applies to the next
    # purchase and is debited at mark_paid — the full earn→spend loop in one run. ──
    available_before = summary["availableCreditMinor"]
    quote = referrer.get("/verifications/quote", params={"tier": "BASIC", "currency": "NGN"}).json()["data"]
    check("cleared credit auto-applies to the referrer's next quote (§17.1)",
          quote["referralCreditAppliedMinor"] > 0,
          f"applied={quote['referralCreditAppliedMinor']}")
    check("credit-bearing quote still reconciles (net = price − discounts)",
          quote["netPriceNgnMinor"] == quote["priceNgnMinor"] - quote["totalDiscountMinor"])

    draft = referrer.post("/verifications/draft").json()["data"]
    referrer.post(f"/verifications/{draft['id']}/submit", json={
        "property": {"property_type": "LAND", "address": "8 Bourdillon Rd, Ikoyi",
                     "state": "Lagos", "lga": "Eti-Osa", "landmark": "Near the towers"},
        "tier": "BASIC", "currency": "NGN",
        "consent": {"consent_version": consent_version_for("VERIFICATION_TERMS")},
    }).raise_for_status()
    pay = referrer.post(f"/payments/initiate/{draft['id']}", json={"method": "CARD"}).json()["data"]
    referrer.post("/payments/stub/confirm",
                  json={"tx_ref": pay["txRef"], "succeeded": True}).raise_for_status()
    after = referrer.get("/referrals/me").json()["data"]
    check("applied credit is debited from the balance at payment (§17.1, mark_paid)",
          after["availableCreditMinor"] < available_before,
          f"before={available_before} after={after['availableCreditMinor']}")

    # Abandonment sweep is callable + idempotent (§17.1) — reminder emails for stale drafts.
    ab = admin.post("/admin/verifications/sweeps/abandonment").json()["data"]
    check("abandonment sweep runs (§17.1)", "reminded" in ab, f"reminded={ab.get('reminded')}")

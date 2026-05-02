# Decision Log

> Binding decisions for Veriprops PRD execution. Every entry is `proposed` (orchestrator's default — may be overridden by user) or `confirmed` (user-approved). The orchestrator MUST NOT proceed past a phase whose blocking decisions are still `proposed` for any user-input-required item.

---

## Decision: D1 — Versioned consent ownership

**Status:** proposed (Open Q29)

### Context
PRD §3.2 requires every legal document to be versioned and every user acceptance recorded against that exact version. Someone has to *publish* version bumps and *trigger* re-consent prompts. This shapes Phase 0 schema and Phase 2/5/10 UX.

### Options Considered
1. Engineering owns version numbers via migration (`ConsentDocument` rows added in Alembic).
2. Super Admin publishes new versions via admin UI; system fans out re-consent prompts on next relevant action.
3. Hybrid: engineering seeds initial versions; Super Admin publishes subsequent updates via admin UI.

### Chosen Option
Option 3 — Hybrid.

### Rationale
- Initial versions need to ship with the migration (Phase 0/2 require functional consent at signup).
- Subsequent updates should not require an engineering deploy — they are content changes.

### Tradeoffs
- **Pros:** unblocks MVP; ongoing legal updates are admin-driven.
- **Cons:** two write paths to the consent store — must be carefully serialised to prevent version skew.

### Constraints Introduced
- `ConsentDocument` carries `version` (semver) + `published_by` (user_id or `system`) + `published_at` + `effective_at`.
- Re-consent triggers compare `effective_at` against the user's most recent `accepted_at` for that doc type.

### Revisit Conditions
- After Phase 19 — if NDPR audit reveals weakness in admin-published versions, may force engineering-only updates.

---

## Decision: D2 — Trust Score weighting formula

**Status:** **REQUIRES USER INPUT** (Open Q8, Q32)

### Context
Phase 8.5 needs a deterministic composite trust score (0–100) computed from per-agent role scores. PRD says "weights admin-defined" but does not give initial values, weights per role, or formula shape (weighted mean, capped sum, geometric mean, etc.).

### Options Considered
1. Weighted arithmetic mean per role: `Σ(score_role × weight_role) / Σ(weight_role)`.
2. Geometric mean (penalises any single low-scoring role harder).
3. Capped sum with floor (e.g., minimum across roles is the score floor — protects against one bad task hiding behind good others).
4. Hybrid — weighted mean modified by minimum-floor bound.

### Chosen Option
*Pending user input.* Provisional default: Option 1 (weighted arithmetic mean) with weights:
- Basic tier (Registry only): Registry = 1.0
- Standard tier: Registry 0.30, Field 0.30, Surveyor 0.40
- Premium tier: Registry 0.20, Field 0.20, Surveyor 0.30, Lawyer 0.30

### Rationale (provisional)
Weighted mean is the simplest auditable formula. Lawyer carries the highest weight in Premium because it's the legal-opinion seal. Surveyor weight is elevated when present — a wrong boundary is the most actionable risk for a buyer.

### Tradeoffs
- Pros: easy to explain; admin-tuneable.
- Cons: cannot model "Lawyer disagrees with Registry" — that conflict is out-of-band (Phase 8.2 conflict detection).

### Constraints Introduced
- Weights table is admin-configurable per tier × role (Phase 18 UI).
- Score is recomputed on `Approve` of any task in `UNDER_REVIEW`.

### Revisit Conditions
- After 50 completed verifications — examine score distribution + dispute correlation.

---

## Decision: D3 — Trust score visibility to agents pre-submit

**Status:** **REQUIRES USER INPUT** (Open Q9)

### Context
PRD §7 has agents input their own trust score. Should they see the rolling composite score before they submit?

### Options Considered
1. Agents see their score input only; never see composite.
2. Agents see composite only after submit + admin approval.
3. Agents see live composite as it builds (their score + others already submitted).

### Chosen Option
*Pending.* Provisional default: **Option 2** — agents see composite only after admin approval, to prevent gaming.

### Rationale
Live visibility creates an incentive to optimise toward the score rather than the truth. Post-approval visibility is feedback without distortion.

### Revisit Conditions
- If agent satisfaction drops; if dispute rate correlates with low feedback transparency.

---

## Decision: D4 — Payment gateway selection

**Status:** **REQUIRES USER INPUT** (Open Q13)

### Context
Both Paystack and Flutterwave SDKs are wired in `appodus_utils/integrations/payment/`. Which is primary for NGN cards? Which handles multi-currency + international wires?

### Options Considered
1. Paystack only — NGN-strong, mature; but USD/GBP/EUR support weaker.
2. Flutterwave only — multi-currency native, but NGN-card UX historically weaker.
3. **Hybrid** — Paystack for NGN cards, Flutterwave for multi-currency.

### Chosen Option
Provisional: Option 3. Selected at runtime via `ACTIVE_PAYMENT_METHOD` per currency context.

### Rationale
Lets us optimise per-currency. The customer's tier-card flow picks the gateway based on selected currency.

### Tradeoffs
- Pros: best UX per currency.
- Cons: two webhooks to maintain; reconciliation across two providers.

### Revisit Conditions
- If reconciliation overhead grows past 5% of finance-admin time.

---

## Decision: D5 — SMS provider selection

**Status:** **REQUIRES USER INPUT** (Open Q14)

### Context
Both Twilio and Termii integrations are in `appodus_utils/integrations/`. Termii is Nigeria-specialised; Twilio is global.

### Options Considered
1. Termii only — best NG deliverability, lower cost.
2. Twilio only — global reach for diaspora SMS confirmations.
3. **Hybrid** — Termii for Nigerian numbers, Twilio for international.

### Chosen Option
Provisional: Option 3 — route by country code.

### Rationale
Diaspora customers receive SMS at international numbers (Twilio); Nigerian agents receive SMS at NG numbers (Termii).

### Revisit Conditions
- If unified deliverability via one provider drops below 95%.

---

## Decision: D6 — BVN verification provider

**Status:** **BLOCKING — REQUIRES USER INPUT** (Open Q15)

### Context
Phase 3 KYC requires live BVN verification. Mono / Dojah / Okra are the three commonly-cited Nigerian providers. They differ on price, latency, fraud-detection extras, and selfie-match availability.

### Options Considered
1. **Mono Connect** — broad financial-data API; BVN endpoint mature.
2. **Dojah** — KYC-focused; bundles BVN + selfie match + ID verification in one SDK.
3. **Okra** — financial data leader; less KYC-bundled.

### Chosen Option
*Cannot proceed without user input.* Provisional recommendation: **Dojah** — KYC-bundled simplifies vendor management and addresses Q16 (selfie match) at the same time.

### Tradeoffs
- Pros (Dojah): one vendor, one webhook, one billing relationship.
- Cons (Dojah): BVN-only price arguably higher; less mature financial-data side.

### Revisit Conditions
- If false-rejection rate > 3% in pilot.

---

## Decision: D7 — Selfie match technology

**Status:** **BLOCKING — REQUIRES USER INPUT** (Open Q16)

### Context
Phase 3 selfie match against BVN photo or uploaded ID. Build vs buy.

### Options Considered
1. Vendor-bundled (Dojah / Smile Identity / Verifyle).
2. AWS Rekognition (CompareFaces) — pay-per-call.
3. In-house (face-recognition lib + ML pipeline) — defer.

### Chosen Option
Provisional: vendor-bundled with the BVN provider (D6).

### Rationale
Build is out of scope for MVP. Vendor accuracy is good enough; costs are predictable.

### Revisit Conditions
- If vendor pricing shifts; if false-match rate > 0.1%.

---

## Decision: D8 — OAuth providers in production

**Status:** confirmed-by-default (Open Q18)

### Context
Phase 2 §2.2 lists Google, Apple, Facebook with `NEXT_PUBLIC_OAUTH_{...}_DISABLED` per-provider flags so a provider can be hidden while developer-console approval is pending.

### Chosen Option
- **Google** — enabled in all envs.
- **Apple** — enabled in dev/staging; **prod-disable until Apple developer review approves**.
- **Facebook** — enabled in dev/staging; **prod-disable until Meta App Review approves**.

### Rationale
Mandatory developer-account reviews are slow. The disable flags exist precisely so we can ship without them.

### Constraints Introduced
- Frontend defaults to disabled for Apple + Facebook in `.env.prod`.
- E2E tests still cover all three providers in dev/staging.

### Revisit Conditions
- After Apple + Meta reviews land.

---

## Decision: D9 — OAuth profile data stored (NDPR)

**Status:** **REQUIRES USER INPUT** (Open Q35)

### Context
NDPR requires data minimisation. What OAuth profile fields do we persist?

### Options Considered
1. Only `email`, `oauth_subject_id`, `provider` — minimum needed for re-auth.
2. Above + `display_name`, `avatar_url`, `email_verified_flag`.
3. Full profile (locale, timezone, etc.) — too broad.

### Chosen Option
Provisional: Option 2.

### Rationale
`display_name` and `avatar_url` are needed in the UI and are what users expect a social login to provide. `email_verified_flag` short-circuits OTP step.

### Revisit Conditions
- If NDPR audit objects to `avatar_url` retention.

---

## Decision: D10 — Real-time channel for live dashboard

**Status:** **REQUIRES USER INPUT** (Open Q22)

### Context
Phase 9 customer dashboard needs real-time status updates. WebSocket vs SSE.

### Options Considered
1. **SSE** — server-sent events, one-way (server → client), works over plain HTTPS, no extra infra.
2. **WebSocket** — bidirectional, more capable but requires additional connection management.
3. Polling-only (60-sec) — already required as fallback per PRD.

### Chosen Option
Provisional: **SSE**.

### Rationale
- One-way channel is sufficient — clients only consume status updates.
- Plays nicer with serverless deploy targets (Vercel) than long-lived WebSockets.
- Polling fallback remains for SSE-incompatible browsers.

### Tradeoffs
- Pros: simpler infra; fewer connection-management failure modes.
- Cons: no client → server duplex; if we add agent live-typing later we'll add WebSockets.

### Revisit Conditions
- If we add live messaging (Phase 11) with typing indicators.

---

## Decision: D11 — Pricing defaults

**Status:** **REQUIRES USER INPUT** (Open Q1, Q2, Q3, Q4, Q5, Q6, Q10)

### Context
PRD §1.7 quotes ₦150k / ₦350k / ₦750k for Basic / Standard / Premium. Other knobs (cancellation surcharge, service fee, discounts, price lock) have suggested defaults but no signed-off values.

### Provisional Defaults (admin-configurable)
| Knob | Default |
|---|---|
| Basic tier price (NGN) | ₦150,000 |
| Standard tier price (NGN) | ₦350,000 |
| Premium tier price (NGN) | ₦750,000 |
| Cancellation surcharge | 5% |
| Service fee | 10% |
| First-time discount | 5% |
| Referral credit (referrer) | 5% |
| Referral discount (invitee) | 5% |
| Max combined discount cap | 15% |
| Price-lock window | 24 hours |

### Rationale
PRD-quoted values where stated; conservative defaults elsewhere. All knobs are admin-configurable in Phase 18 — initial values are seeded via migration.

### Revisit Conditions
- After first 100 verifications — re-tune by conversion rate.

---

## Decision: D12 — FX rate source

**Status:** **REQUIRES USER INPUT** (Open Q11)

### Context
Currency toggle needs live or near-live FX. Two paths: live API or admin-set table updated daily.

### Options Considered
1. Live API (e.g., openexchangerates.org or fixer.io) with 5-min cache.
2. Admin-set rate table refreshed daily by Finance Admin.
3. Hybrid — API source with admin override capability.

### Chosen Option
Provisional: **Option 3**.

### Rationale
- Live API is essential for diaspora-facing pricing accuracy.
- Admin override is a safety net for rate spikes / API outages.
- Stale-warning at 30 min (per PRD §5.2) covers the failure mode.

### Revisit Conditions
- After first FX-API outage — may move to admin-only.

---

## Decision: D13 — Listing-URL parser supported sites

**Status:** **REQUIRES USER INPUT** (Open Q17)

### Context
PRD §5.1 names PropertyPro and Nigeria Property Centre. Are others required for MVP?

### Chosen Option
Provisional: PropertyPro + Nigeria Property Centre **only** for MVP.

### Rationale
Two sites cover ~80% of diaspora-targeted listings. Manual fallback handles the rest.

### Revisit Conditions
- After 30 days post-launch — review parser-success rate per source.

---

## Decision: D14 — Country/timezone source dataset

**Status:** **REQUIRES USER INPUT** (Open Q19)

### Context
Signup auto-suggests timezone from country.

### Chosen Option
Provisional: **`Intl.supportedValuesOf('timeZone')`** for browsers + IANA TZ database server-side. Country list from ISO 3166-1.

### Rationale
- IANA / ISO are authoritative, no third-party dependency.
- Frontend uses native browser APIs.

---

## Decision: D15 — Conflict-detection initial rule set

**Status:** **REQUIRES USER INPUT** (Open Q20)

### Context
Phase 8.2 needs an initial rule set for automated conflict flags between agent submissions on the same verification.

### Provisional Initial Rules
1. **Occupancy mismatch** — Field reports occupied; Registry reports vacant per ownership records.
2. **Boundary divergence** — Surveyor coordinates differ from Registry survey-plan coordinates by > 5m.
3. **Authenticity conflict** — Lawyer flags forged document; Registry flagged document as authentic.
4. **Owner-name mismatch** — Registry chain shows different owner than seller info on customer submission.

### Constraints Introduced
- Each rule produces a `conflict_flag` that admin must resolve before "Release Report" is permitted.

### Revisit Conditions
- After 20 verifications — review false-positive rate per rule.

---

## Decision: D16 — Wire proof reconciliation

**Status:** **REQUIRES USER INPUT** (Open Q21)

### Context
Phase 5.4 wire proof workflow.

### Options Considered
1. Manual review by Finance Admin only.
2. Auto-match by reference + admin confirm exceptions.
3. Vendor-mediated (e.g. Stripe wire matching).

### Chosen Option
Provisional: **Option 1** for MVP, evolving to Option 2 in Phase 18 once volume justifies it.

### Rationale
Wire proof volumes will be small early; manual review is fastest to ship.

---

## Decision: D17 — Admin SLAs

**Status:** **REQUIRES USER INPUT** (Open Q23, Q24, Q25, Q33)

### Provisional Defaults
| SLA | Default | Phase |
|---|---|---|
| Agent application review | 3 business days | 3 |
| Agent no-show timeout | 4 hours | 7 |
| Max active task capacity per agent | 5 | 16 |
| Admin report-release SLA | 4 hours | 8 |

### Rationale
Match PRD's suggested values.

### Revisit Conditions
- If admin operations bottleneck on application review — extend or add Operations capacity.

---

## Decision: D18 — KYC document review (manual vs automated)

**Status:** **REQUIRES USER INPUT** (Open Q27)

### Context
Phase 3 ID upload (NIN / Passport / DL / Voter's Card) — review path.

### Chosen Option
Provisional: **Vendor-automated (D6) primary; admin manual fallback for low-confidence results.**

### Rationale
Most cases auto-resolve. Admin attention reserved for vendor's "uncertain" tier.

---

## Decision: D19 — Verification Disclaimer copy

**Status:** **BLOCKING — REQUIRES USER INPUT** (Open Q28)

### Context
Phase 5 cannot ship pre-payment without legally-signed-off Verification Disclaimer copy. The five consent items (PRD §5.3) need final wording.

### Required Action
Legal sign-off on:
1. Verification Disclaimer
2. Findings & Opinion Acknowledgement
3. Jurisdiction & Platform-Only Transactions
4. Communication Recording
5. Refund & Cancellation Policy

### Constraints Introduced
- Until copy is signed, Phase 5 launch is gated.
- Initial versions will be seeded via migration; subsequent updates via admin UI (per D1).

---

## Decision: D20 — Trust-status visibility to other users

**Status:** **REQUIRES USER INPUT** (Open Q30)

### Context
A user's `trusted` flag — is it visible to others (e.g. on report), to admins only, or hidden entirely?

### Provisional Default
Visible to admins only. Not surfaced to customers or other agents.

### Rationale
"Trusted" is a system-internal signal that drives ranking (Phase 16) and could be gamed if exposed.

---

## Decision: D21 — Area Insights content owner

**Status:** **REQUIRES USER INPUT** (Open Q31)

### Context
Phase 18.4 includes per-LGA Area Insights as content. Source + maintainer?

### Provisional Default
Operations Manager curates; CMS UI in Phase 18 for content edits.

### Revisit Conditions
- If LGA coverage exceeds 20 areas, may need content team.

---

## Decision: D22 — Share link default expiry

**Status:** confirmed-by-default (Open Q34)

### Chosen Option
30 days default; customer can extend or revoke. Phase 18 may add admin override per share class.

### Rationale
Match PRD §13.2.

---

## Decision: D23 — Nigerian public holidays for SLA exclusion

**Status:** **REQUIRES USER INPUT** (Open Q26)

### Context
SLA timers must exclude Nigerian public holidays. Source list?

### Provisional Default
Maintained as a `business_calendar` table seeded from Nigerian Federal Government public-holiday list, refreshed annually by Operations Admin in Phase 18.

### Constraints Introduced
- `business_calendar` entity in Phase 0 schema.
- Seed migration carries 2026 + 2027 holidays.

---

## Decision: D24 — Re-check pricing model

**Status:** **REQUIRES USER INPUT** (Open Q7)

### Context
Phase 14.1 re-check pricing. Three models:
1. Flat fee per re-check.
2. Per-affected-agent fee.
3. Percentage of original verification price.

### Provisional Default
**Per-affected-agent fee** — sum of per-task component prices for tasks scoped into the re-check. Configurable in Phase 18.

### Rationale
Aligns cost with actual work; avoids charging customer for tasks that did not need re-doing.

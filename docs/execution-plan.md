# Execution Plan — WhatsApp Channel (cycle 2)

> Vertical slices (backend + migrations + tests + frontend, demoable end-to-end). Batch sizing per
> skill rules: schema/auth/integration slices are small; flow/UI slices medium-large. Cycle-1 plan
> archived at `docs.back/execution-plan.md`. Requirement ids → `requirements-matrix.md`.

## Slice S1 — Website chat widget + attribution

### Objective
§7.4.1 live immediately against the concierge-phase number: floating WhatsApp button on all public
+ authenticated pages except payment routes, wa.me deep link with page-code prefill.

### Requirements Covered
WA-18, WA-19, WA-01 (site pledge copy), WA-02 (number from single config source)

### Dependencies — none (independent)
### Files Impacted
`frontend/src/components/` shared layout/AppShell + new `WhatsAppWidget`; route-aware suppression
via the route registry (`frontend/src/lib/routes.ts`); official number + page codes in one config module.
### Schema / API Changes — none
### Tests Required
vitest render/suppression/aria; Playwright a11y + zero-CLS check; page-code table unit test.
### Acceptance Criteria
Widget everywhere except payment flow; opens wa.me with correct prefill; no layout shift.
### Risk — Low
### Commit — `feat(whatsapp): site-wide WhatsApp widget with page-code attribution (S1)`

## Slice S2 — Channel foundation: webhook receiver + facade transports + inbound console path

### Objective
Signature-verified Meta webhook (hub handshake + HMAC over raw body), inbound normalization,
`WHATSAPP_PROVIDER=STUB|META` selection, deterministic stub transport with dev-endpoint injection,
and WhatsApp-sourced messages landing in the existing admin console with source labeling.

### Requirements Covered
WA-09, WA-10, WA-12 (inbound half), WA-13, WA-05

### Dependencies — none
### Files Impacted
`app/domain/channel/whatsapp/webhook/`; `appodus_utils/integrations/messaging/providers/whatsapp/`
(reuse `whatsapp_business.py`, add `stub.py` + inbound models); `app/domain/communication/`
source labeling; `app/domain/dev/` inbound-injection endpoint (double prod gate); Alembic migration
(source label, inbound log); edge-auth exemption for the webhook path (backend + `proxy.ts` note).
### Schema Changes
chat message source/channel column; webhook inbound log table (or reuse messages bookkeeping).
### Tests Required
signed-fixture webhook tests (valid/invalid/replayed), normalization units, fraud-scan-on-WA test,
e2e: injected inbound appears in admin console via SSE.
### Risk — High (public unauthenticated surface) → small batch
### Commit — `feat(whatsapp): signature-verified webhook, stub/live transports, console inbound (S2)`

## Slice S3 — Handoff token service + /wa/* landing pages

### Objective
§7.5 token service (RS256, 15-min, jti single-use, intent+case scope) + the three token-gated
landing routes with origin acknowledgment and friendly expiry/recovery page.

### Requirements Covered
WA-14, WA-28, WA-20

### Dependencies — S2 (facade for "get a new link" deep link)
### Files Impacted
`app/domain/channel/whatsapp/handoff/`; keypair settings (+`SECRET_ENV_KEYS`, env hygiene test);
migration for redemptions; frontend `/wa/{pay,upload,report}/[token]` routes + expiry page.
### Tests Required
unit: expiry, replay, wrong-intent, wrong-case, tampered signature; e2e: token → pay page with
context banner; reused token → recovery page. Pen-check list drafted (launch gate §7.11).
### Risk — High → small batch
### Commit — `feat(whatsapp): RS256 single-use handoff tokens and /wa landing pages (S3)`

## Slice S4 — OTP account linking (E1) + number lifecycle

### Objective
Web→WhatsApp and WhatsApp→web linking; 1:1 constraint; number-change re-verification; old thread
goes cold.

### Requirements Covered
WA-23, WA-24, WA-25, part of WA-22

### Dependencies — S2 (send OTP via facade), S3 (signed web link for WA→web)
### Files Impacted
`WhatsAppLink` entity + migration; linking endpoints under user/auth; account-settings UI;
`otp_auth` template registry stub use; `TODO(gap): SMS fallback` (D46).
### Tests Required
unit: 1:1 enforcement, re-link, cold-thread; e2e both directions under deterministic OTP.
### Risk — High (auth) → small batch
### Commit — `feat(whatsapp): OTP cross-channel account linking (S4)`

## Slice S5 — Bot engine core: sessions, welcome, FAQ, status, escalation, failure fallback

### Objective
Deterministic flow FSM with per-conversation sessions; welcome (disclosure + pledge + menu);
FAQ/pricing from content set; status flow with short-code disambiguation and unlinked-number
defense; human escalation w/ G1-hours copy; health-checked failure auto-reply + console alert;
intent-classifier facade (STUB + provider-agnostic LLM adapters, D48).

### Requirements Covered
WA-03, WA-04, WA-07, WA-08, WA-11, WA-17, WA-22, WA-29, WA-30, WA-33, WA-36, WA-37, WA-39, WA-40

### Dependencies — S2, S4
### Files Impacted
`app/domain/channel/whatsapp/bot/` (sessions entity + migration, flows, guardrails);
`appodus_utils/integrations/intent/`; content-set storage; §7.3.2 projection function (D45).
### Tests Required
per-flow units; adversarial guardrail suite (judgment requests, non-English, classifier failure);
capability-matrix denial tests; e2e conversation scripts on stub; failure drill (kill bot →
auto-reply + alert).
### Risk — High → medium batches, flows landed incrementally
### Commit — `feat(whatsapp): guardrailed bot engine with LLM-assisted intent facade (S5)`

## Slice S6 — Intake flow + payment handoff + website→WhatsApp continuation

### Objective
Chat intake writing the canonical case via shared services; resumable on both surfaces; completion
→ `pay` token handoff with pledge + domain-check; "Continue on WhatsApp" affordances with opaque
short codes.

### Requirements Covered
WA-31, WA-32, WA-21, WA-01 (handoff pledge)

### Dependencies — S3, S5
### Files Impacted
bot intake flow reusing submission-draft services; short-code issuance on verification; dashboard
+ mid-wizard continuation UI.
### Tests Required
e2e: start in chat → finish on web; start on web → finish in chat; handoff message contents;
short-code opacity unit test.
### Risk — Medium
### Commit — `feat(whatsapp): resumable chat intake with payment handoff (S6)`

## Slice S7 — Console adapter completion: agent replies, 24h window, non-text inbound

### Objective
Agent console replies out through the facade; `window_reopen` template outside Meta's 24-hour
window; §7.6.3 non-text handling (images → evidence rule + upload token, unofficial flag; voice →
flagged audio routing; pins/contacts → human).

### Requirements Covered
WA-12 (complete), WA-06, WA-38, WA-41 (window_reopen wiring)

### Dependencies — S3 (upload token), S5
### Files Impacted
`communication/` reply path + window tracking; console UI source labels + unofficial-media badge +
audio flag.
### Tests Required
unit per media type; window boundary unit; e2e: admin reply reaches stub outbound; image inbound
never links to evidence.
### Risk — Medium
### Commit — `feat(whatsapp): full console mediation, 24h window handling, non-text policy (S7)`

## Slice S8 — Template registry, consent capture, milestones, report delivery

### Objective
§7.7 registry (seeded, approval-tracked, admin UI); §7.4.6 dual unticked consents at payment
confirmation + settings + STOP keywords; router-enforced consent; milestone templates on domain
events; report-ready delivery (WhatsApp opt-in + unconditional email).

### Requirements Covered
WA-15, WA-16, WA-27, WA-34, WA-35, WA-41 (registry)

### Dependencies — S5; S6 (consent placement at payment confirmation)
### Files Impacted
template entity + migration + admin DataTable page; consent domain extension; notification rule
table + subscribers; payment-confirmation UI.
### Tests Required
router consent-gate units (never send-site enforcement); STOP keyword flow; event→template units;
e2e milestone + report delivery on stub; email-always assertion.
### Risk — Medium
### Commit — `feat(whatsapp): template registry, dual consent, event-driven milestones (S8)`

## Slice S9 — Delegates (O2 slim)

### Objective
One OTP-verified delegate per case: authorize from case detail, status-milestones only, instant
revoke, bot role identification, social-engineering defense for non-delegates.

### Requirements Covered
WA-26

### Dependencies — S4 (OTP mechanics), S8 (delegate_status template)
### Files Impacted
`CaseDelegate` entity + migration; case-detail UI; bot delegate flow; router delegate audience.
### Tests Required
units: one-per-case, revocation-next-event, scope denial (docs/report/chat/intake never sent);
e2e delegate lifecycle; adversarial non-delegate enquiry test.
### Risk — Medium-High (access control) → small batch
### Commit — `feat(whatsapp): slim per-case delegates with status-only visibility (S9)`

## Slice S10 — Channel analytics

### Objective
§7.10 instrumented from day one of launch: seam conversion, widget-attributed enquiries,
enquiry→intake rate, escalation rate + reasons, opt-in rates, quality-rating placeholder,
voice-note volume; admin analytics surface.

### Requirements Covered
WA-43, WA-19 (attribution consumption)

### Dependencies — S5–S9 (events to count)
### Files Impacted
analytics domain extension (server-derived, backend source of truth); admin analytics page.
### Tests Required
metric derivation units; e2e smoke on dashboards.
### Risk — Low
### Commit — `feat(whatsapp): channel analytics (S10)`

## Slice S11 — Live hardening & launch-gate closeout

### Objective
Exercise the live Meta path (D43) once assets exist: live smoke on send/receive/template flows,
token pen-check execution, failure drill on live config, env hygiene + docs; compliance copy
(§7.8) landed; launch checklist in progress.md updated; MASTER-PRD §7 incorporation + CLAUDE.md
pattern notes.

### Requirements Covered
WA-02, WA-40 (live), WA-42, WA-44

### Dependencies — all prior; external Meta assets (⊘)
### Tests Required
pen-check list executed; live smoke script (manual/gated, never CI); e2e full-suite green on stub.
### Risk — Medium (external-dependency bound)
### Commit — `chore(whatsapp): live-path hardening and launch-gate closeout (S11)`

---

## External prerequisites (tracked, non-blocking for S1–S10)
Meta Business verification + green tick · template approvals (draft early — S8 registry holds
status) · number custody (+2349167624347) · Doppler secrets (WHATSAPP_*, RS256 keypair,
intent-provider API key(s)) · counsel items (§7.8 retention, ToS copy).

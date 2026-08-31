# Veriprops — Full-System UAT Strategy (Playwright Browser Suite)

Status: **implementation in progress** — the suite foundation and the first two areas are built and green ([frontend/e2e/](../frontend/e2e/)); the remaining areas are backlog. See [§12 Implementation status](#12-implementation-status) for what exists today, what is proven, and what comes next. This document remains the definition of *what* the browser-driven User Acceptance Test suite must cover and *how* it is structured.

## Context

Veriprops has a mature deterministic-automation foundation (deterministic OTP `654123`, `/dev/reset` + `/dev/seed`, ~83 files of `data-testid` selectors, `window.__*` automation hooks, Mailpit capture) — but **no browser-driven test exists anywhere in the repo**. What is currently called "e2e" ([backend/scripts/e2e_drive_through.py](../backend/scripts/e2e_drive_through.py), wired into [.github/workflows/e2e.yml](../.github/workflows/e2e.yml)) drives the **backend API directly over HTTP** across 17 staged scripts; it never renders a page or clicks a button. So the *user-facing* behaviour — what a customer, agent, or admin actually does in a browser — has **never been validated end-to-end**. This suite is net-new UI coverage, not a duplicate of the API drive-through.

UAT here means *acceptance*: business-readable scenarios, each traceable to a PRD requirement, with an explicit pass/fail definition.

**Locked decisions:** all 20 PRD areas as one flat backlog (no product phasing) · one shared seeded scenario per full suite run · local/manual runs only (no CI wiring yet) · **automated Playwright suite only** — a green suite *is* the acceptance signal, there is no separate manual/stakeholder pass · **full engine matrix** — Chromium + WebKit + Firefox, desktop and mobile · **accessibility in scope as first-class acceptance criteria** (axe-core across covered flows) · **`/dev/seed` extended** as an explicit workstream (RBAC admins, pagination volume, per-area fixtures) alongside API-bootstrap helpers.

---

## 1. Acceptance model (what "UAT pass" means)

- **Automated-only acceptance.** No separate manual/stakeholder pass: a **green suite across the full engine matrix is the acceptance signal**. Every acceptance criterion must be an automated assertion, and the coverage matrix (below) is what a stakeholder reviews to trust that green means accepted.
- **Traceability.** Every scenario carries a stable id `UAT-<AREA>-<n>` and a PRD reference (`§10.5`, etc.). A coverage matrix (scenario → PRD section, with pass/fail + last-run) proves completeness.
- **Pass/fail.** A scenario passes only when its **business-observable outcome** is asserted through the UI (rendered state, visible label, downloadable artifact, email in Mailpit) — never merely "no error thrown." Assertions prefer the documented customer-facing state labels (PRD §14) and `data-testid` anchors. **Every covered page additionally passes an axe-core a11y assertion** (§7).
- **Risk tiering (within the single flat backlog).** Areas are tagged **P0/P1/P2** by business risk so partial runs still cover what matters. Flat backlog = no phased product rollout; risk tags are prioritization metadata only.
  - **P0 (money + trust + identity):** Auth/Sessions, Submission & Payment, Review/Trust-Score/Release, Earnings/Payouts, Disputes, Audit/NDPA-Erasure, Public Lookup (data-leak surface), **Authorization/ownership boundaries** (cross-cutting, §6a).
  - **P1 (core operating flows):** Agent Onboarding/KYC, Admin RBAC, Verification Ops, Agent Task Execution, Customer Tracking, Report Experience, Communication/Chat, Notifications, Re-check/Upgrade.
  - **P2 (supporting):** Marketing/Public, Reputation/Coverage, Growth/Referral, Admin Analytics/Config/Broadcasts.
- **Run report (every run):** coverage matrix 100% attempted; all P0 green on all engines; every non-green triaged as *defect* vs *known-gap (PRD §G)* vs *environment/flake*; Playwright HTML report + trace + screenshot + video retained per failure (§8a).

---

## 2. Foundations the suite builds on (do not reinvent)

| Capability | Where | UAT use |
| --- | --- | --- |
| Deterministic OTP `654123` | `TEST_OTP`, `OTP_MODE=deterministic` | Fill every OTP field literally; never read an inbox for OTP. |
| Reset + seed | `POST /dev/reset`, `POST /dev/seed` ([backend/main/app/domain/dev/](../backend/main/app/domain/dev/)) | One reset+seed in Playwright `globalSetup`. |
| Message inspect / rewind | `GET /dev/messages/latest`, `POST /dev/messages/rewind` | Assert dispatch; fast-forward retry backoff without timers. |
| Seeded accounts | `seed()` | `qa-customer@`, `qa-agent-{registry,field,surveyor,lawyer}@`, `qa-erasable@veriprops.io` (`Test1234!`); super-admin from `SUPER_ADMIN_EMAIL`/`_PASSWORD`. |
| Seeded verifications | `seed()` | Primary `UNDER_REVIEW` SLA-overdue (tasks review-approved → drive release/report-review) + `IN_PROGRESS` "ops" verification pre-crafted for no-show / pool-starvation / decline / fail / chargeback. |
| Selectors | `{flow}-{element}` testids; canonical routes in [frontend/src/lib/routes.ts](../frontend/src/lib/routes.ts) | Primary selector strategy; never text/CSS where a testid exists. |
| Window hooks | [frontend/src/lib/automation.ts](../frontend/src/lib/automation.ts) | `__app_ready__` (ready gate), `__auth_snapshot__` (assert auth), `__oauth_complete__` (OAuth terminal), `__TEST_MODE__`. Live only when `NEXT_PUBLIC_ENVIRONMENT ∈ {dev_personal, development, test}`. |
| Email | Mailpit REST `:8025` | Invites, recovery, share links, reset tokens. |
| Stubs | `PAYMENT_STUB_MODE=True`, KYC/storage/FX/payout stubs | Assert stub paths only. |

---

## 3. Suite architecture (for implementation)

New top-level `frontend/e2e/` with `playwright.config.ts`, `global-setup.ts`, `fixtures/`, `helpers/`, and `specs/` grouped by feature area.

**Reconciling "shared seed per run" with resilience — the core design decision:**

1. `globalSetup` runs **one** `/dev/reset` + `/dev/seed` → the deterministic baseline for the whole run.
2. Each persona logs in once; auth is persisted with Playwright **`storageState`** (`customer.json`, `agent-{role}.json`, `admin.json`) and reused, so specs don't re-login.
3. **Every spec is independently bootstrappable.** A spec that needs a precondition the seed doesn't provide (e.g. "a verification already at PAID") creates it via **API setup helpers** in its own `beforeEach`, not by depending on an earlier spec's UI actions. The shared seed is a *fast default*, not a hard chain — a failure in spec N never blinds specs N+1…, and any spec can run alone with `--grep`.
4. Ordering: use Playwright **project dependencies** so the golden-path backbone (§4) runs first and its produced ids are published to a run-scoped fixture; branch specs consume those ids **or** self-bootstrap if absent. Config runs single-worker / `fullyParallel:false` for shared-state areas (the isolation decision), but the self-bootstrap rule makes this a performance choice, not a correctness dependency.

**Helper layer to build once:** `login(page, persona)`, `waitReady(page)` (`__app_ready__`), `authSnapshot(page)`, `resetAndSeed()`, `api(persona)` (thin authenticated HTTP client for preconditions/teardown, mirroring `e2e/harness.py`), `mailpit(recipient)`, `stubPay(page)`, `runSweep(name)` (admin sweep triggers), `portalSwitch(page, persona)`.

**Selector rule:** extend the existing `{flow}-{element}` testid convention. A prerequisite audit (§8) enumerates which areas already have complete testid coverage; missing anchors are a scoped frontend change listed before the dependent specs.

---

## 4. The golden-path lifecycle backbone (the spine every area hangs off)

One ordered cross-persona journey exercised through the browser — the single most valuable UAT artifact, and the producer of shared state:

1. **Customer** signs up (email OTP `654123`) → submits a STANDARD verification (Property → Tier → Consent) → pays via stub → lands on confirmation with SLA countdown.
2. **Admin** assigns the per-role tasks (suggested-agents + capacity cap) from the control panel.
3. **Agents** (per role) accept → start → submit role-specific forms with ≥1 evidence item; Lawyer task unlocks only after siblings SUBMITTED.
4. **Admin** reviews each task (reject-with-reason round-trip on one, then approve), resolves any conflict flag, then **Release Report**.
5. **Customer** sees the report unblur after `REPORT_DISCLAIMER`, downloads the PDF, and the trust-score gauge renders.
6. **Customer** files a dispute (or requests re-check) → **Agent** defends in the 48h window → **Admin** resolves.

Each numbered step is also the entry point for that area's deeper scenario matrix (§6). PREMIUM-tier and re-check/upgrade variants reuse the same backbone with tier/version deltas.

---

## 5. Time & real-time determinism (and its coverage boundary)

The codebase has **no general business clock**. Time-dependent state is producible only two ways, and UAT must live within that:

- **Backdated seed fixtures** — `seed()` crafts the SLA-overdue primary verification and the ops-verification tasks with already-blown deadlines.
- **Trigger endpoints** — admin sweeps `POST /admin/verifications/sweeps/no-show`, `.../pool-starvation`, the SLA-breach sweep, `POST /messages/sweeps/retries`, plus `POST /dev/messages/rewind` (pulls `next_retry_at`/`expires_at` into the past). Claim-based and idempotent, so a spec drives them directly in setup.

**SSE / real-time:** assert on the **resulting DOM state** (via `__app_ready__`/re-render and the 60s poll fallback), not on the raw event stream. Live-update scenarios trigger the change through one persona's action and assert another persona's already-open page reflects it within the poll window.

**Coverage boundary (must be stated in the run report):** multi-day windows with **no** backdated-seed or trigger hook — 24h price-lock expiry, 7-day commission/credit clearance, 10%/120-day chargeback reserve release, 30-day dispute window — **cannot be advanced through the UI deterministically today.** Options in priority order:

1. Cover these at the **API level** (the Python drive-through already asserts the transitions) and mark them "API-covered, not UI-UAT-able" in the matrix. *(Default — no new code.)*
2. If UI UAT of a specific window is required, add a **seed variant** that backdates that entity (mirrors the existing SLA-overdue fixture pattern).
3. Only if broad time control is needed, introduce a guarded `/dev` time-travel endpoint — a larger change, out of scope here.

---

## 6. Scenario matrices — 20 areas (flat backlog, risk-tagged)

**Template:** `id · PRD-ref · risk · persona(s) · precondition (seed or API-bootstrap) · steps (testid-anchored) · expected (business-observable) · exclusions`

**Worked example A — `UAT-PAY-03` · §10.5 · P0 · Customer**
*Precondition:* seeded customer with an unpaid STANDARD draft (API-bootstrap if absent).
*Steps:* open `/portal/verifications/[id]/pay`; complete phone-verification OTP (`verify-pay-otp` = `654123`); initiate card payment (`verify-pay-initiate`); confirm on stub checkout (`verify-pay-confirm`).
*Expected:* page shows "Payment Confirmed — Agents Being Assigned"; SLA countdown visible; `qa-customer` becomes TRUSTED (assert via `__auth_snapshot__`/account); PAYMENT_CONFIRMED email present in Mailpit.
*Exclusions:* no live Paystack/Flutterwave; card-fingerprint dark under stub.

**Worked example B — `UAT-LEAK-01` · §18 · P0 · unauthenticated**
*Steps:* open `/verify/[vid]` for a SHARED verification; then for PRIVATE, IN_PROGRESS, DISPUTED, and a random NOT_FOUND vid.
*Expected:* SHARED shows only allow-listed fields (VID, badge, trust **band** not number, tier, date, type, state/LGA, version); the other four render **indistinguishable** shapes (no probing signal); full address / agent / owner names / documents / numeric score never appear in any DOM.

**Per-area inventory** (each expands into a matrix like above; **EXCLUDE** = assert stub or skip, never assert as real):

1. **Marketing & Public (§6, P2)** — landing sections; `/about`, `/sample-report`, `/legal/[slug]`; CTA intent (`?intent=verify|agent`) preserved through auth; currency toggle display-only (assert against backend quote, not marketing copy).
2. **Auth & Sessions (§7, P0)** — signup 4-step wizard + resume; login + lockout; forgot/reset (Mailpit token, single-use, session-invalidating); OAuth `__oauth_complete__` lifecycle + email-collision rejection; devices list/revoke/"log out all"; account area (`/account/*`); route protection + portal priority Admin→Agent→Customer.
3. **Agent Onboarding & KYC (§8, P1)** — apply wizard (`agent-apply-*`) roles→KYC(**stub**)→credentials→terms; PENDING blocks jobs until admin approval.
4. **Admin RBAC (§9, P1)** — invite accept (3 cases, Mailpit token); team matrix, deactivate, change sub-role, no self-target, only SUPER grants SUPER; **negative:** non-SUPER forbidden from `/admin/config/system`, invitations, erasure execute.
5. **Submission & Payment (§10, P0)** — wizard + lazy idempotent draft + one-unpaid-in-flight + autosave + cross-device resume; pay page price-lock interstitial, phone gate, card **stub** + NGN transfer `PENDING_TRANSFER`; PAID→TRUSTED + PAYMENT_CONFIRMED. **EXCLUDE:** live gateways.
6. **Verification Ops — Admin (§11, P1)** — control panel DataTable, assign/reassign + capacity cap, broadcast pool first-accept-wins, pause/resume/cancel/declare-failure/extend-SLA; **sweeps via trigger endpoints** (no-show/pool-starvation/SLA); approval queue; admin notes never leak.
7. **Agent Task Execution (§12, P1)** — available/active jobs, commission-before-accept, role forms (`ROLE_FORM_FIELDS`), ≥1 evidence, Lawyer dependency-gate, evidence immutable, conflict/identity capture, Report-Issue escalation; **negative:** agent can't cancel/pause. **EXCLUDE:** offline queue, client compression, image derivatives.
8. **Review / Trust / Release (§13, P0)** — read-only review + gallery; reject→reason+revision auto-posts to admin↔agent thread; approve records quality score but doesn't move state; conflict resolve; **Release Report** atomic flip; **negative:** no report reaches customer pre-release; Request-Changes reopen banner; FAILED (reason+evidence, irreversible, stub refund).
9. **Customer Tracking & Evidence (§14, P1)** — tracking SLA card, progress, agents show **role+first-name+badge only** (negative: no contact details), state-label mapping assertions, milestones surface only post-approval, evidence gallery approved-only tagged by role.
10. **Report Experience (§15, P1)** — disclaimer-gated unblur, header actions, radial gauge, tier-dependent sections, PDF (fpdf2 + QR), superseded watermark. **EXCLUDE:** Legal Opinion (`LEGAL_OPINION_ENABLED=False`).
11. **Communication / Chat (§16, P1)** — CUSTOMER_ADMIN + system breadcrumbs, ADMIN_AGENT read-only-once-approved, GENERAL_SUPPORT; **negative: no customer↔agent chat anywhere**; fraud-scan HELD → admin queue approve/reject; clarifications OPEN→ANSWERED; shared-inbox unread per `last_read_at`. **EXCLUDE:** attachments.
12. **Notifications (§17, P1)** — bell/unread; in-app always-on (can't disable); email/SMS per-event opt-outs; representative triggers assert in-app + Mailpit. **EXCLUDE:** push/WhatsApp.
13. **Public Lookup & Sharing (§18, P0)** — see worked example B; sharing modes Private/Public/`LINK_SUMMARY`/`NAMED_FULL`, expiry + immediate revoke.
14. **Re-check / Upgrade / Disputes (§19, P0 disputes / P1 re-check)** — re-check request→approve+scope→pay secondary→reopen→v2.0; upgrade higher-tier only, price delta, idempotent, v3.0; dispute 30-char/typed/window, freeze commissions, 48h agent defence (never learns identity), outcomes REJECTED/FULL_REFUND/PARTIAL_RECHECK.
15. **Earnings / Payouts (§20, P0)** — commission-before-accept, accrual-at-release double-guarded, balances derived-on-read clamp-at-0, payout request locks funds → finance approve/hold/reject/adjust (`payout-*`). **EXCLUDE (workflow only):** real disbursement (stub marks PAID).
16. **Reputation / Coverage (§21, P2)** — derived metrics, coverage declaration (37-state grid, radius), location-gating Field/Surveyor vs remote Registry/Lawyer, >6-state flag, availability GREEN/AMBER/RED forced-RED-at-capacity, Top-Agent ≥90, sink <40. **EXCLUDE:** real cartography, pool-feed visibility reduction.
17. **Growth / Referral (§22, P2)** — `?ref` capture, invitee 10% first-time discount, referrer ₦5,000 on first payment, cap 25%, self-referral rejected, one recovery email per abandoned draft (Mailpit), price re-lock on return. (Card-fingerprint anti-farm dark under stub — note, don't assert.)
18. **Admin Ops / Analytics (§23, P2)** — Mission Control tiles; analytics CSS bar charts; pricing/commission/trust-weights CRUD (weights sum-to-100 validated); `ConfigKey` system config; broadcasts compose→preview→send/schedule (audience segments).
19. **Audit / Compliance (§24, P0)** — admin action log, PII-safe customer timeline, agent history; audit-pack CSV; consent CSV; NDPA erasure self-request→admin review (SUPER-only, confirm-guarded, idempotent, one-open-per-subject) using `qa-erasable@`.
20. **Dev/QA Contracts (§25, P0 meta)** — smoke-assert seed accounts/verifications exist, OTP resolves `654123`, window hooks present under `dev_personal`, Mailpit capture works — the suite's own trust anchors.

### 6a. Cross-cutting theme — authorization & data-leak boundaries (P0)

Runs against every area. UAT asserts **functional** authorization (pen-testing stays with the `security-review` skill). Representative cases:

- **Ownership/IDOR** — customer A cannot open customer B's `/portal/verifications/[id]`, `/report`, `/evidence`, or messages (403/404, no data leak in DOM); agent cannot open a task not assigned to them.
- **Public-lookup / share leak** — see worked example B; `/shared/[token]` after expiry or revoke shows nothing; `NAMED_FULL` gated to the named recipient.
- **RBAC boundaries** — each non-SUPER admin sub-role (OPERATIONS/FINANCE/CONTENT_*) is allowed exactly its permitted surfaces and forbidden the rest (`/admin/config/system`, invitations, erasure execute are SUPER-only). Requires the seed-extension RBAC admins (§8).
- **Session enforcement through the UI** — device-revoke and reset-time "log out all" actually end an open session on next navigation; logged-out user hitting a protected route redirects.
- **Server-derived identity** — no UI path lets a client set chat `sender_kind` or grant itself an admin sub-role.

### 6b. Automation mechanics for the hard interactions

Named because they are the "will this actually automate?" risks; each becomes a reusable helper:

- **Evidence upload + geolocation** — Playwright `setInputFiles` with committed fixture assets (photo/video/document/signature/certificate) + `context.grantPermissions(['geolocation'])` and `setGeolocation(...)`; assert server-side GPS/timestamp stamping and SHA-256 immutability surface post-submit.
- **PDF report** — capture the download event, then parse the file (PDF text/QR check) to assert VID, version, footer, and QR deep-link — not just that a download occurred.
- **Email-link extraction** — one `mailpit(recipient)` helper fetches the latest message and extracts the reset/invite/share URL from the HTML body to drive token flows.
- **Concurrent pool race** — broadcast pool first-accept-wins needs **two browser contexts** accepting near-simultaneously; assert exactly one wins and the loser sees a capacity/taken state.
- **NGN bank transfer** — the `PENDING_TRANSFER` path is async; the wire-confirmation admin action (or stub webhook) that flips it to PAID is driven explicitly, not assumed.

---

## 7. Cross-browser / device matrix + accessibility

**Engine matrix (full).** Every project runs on **Chromium, WebKit, and Firefox**, each in a **desktop** and a **mobile** device profile (e.g. Pixel 7 for Chromium/Firefox-mobile, iPhone 14/WebKit-mobile) — six project permutations. Because "green = accepted" (§1), a scenario is accepted only when green on **all** engines. This materially raises runtime and engine-specific flake; mitigations in §8a. If runtime becomes untenable, the fallback (decided at implementation, not now) is full P0 on all engines and P1/P2 on Chromium + one mobile — but the standing decision is full-matrix.

**Accessibility (first-class acceptance criteria).** Integrate **axe-core** (`@axe-core/playwright`) as an assertion on **every covered page/state**, not a separate pass: no serious/critical violations is a pass condition. Additionally assert keyboard reachability of primary actions and correct form-label/`aria` associations on the auth, submission, payment, and report flows. A shared `expectNoA11yViolations(page)` helper wraps axe with an agreed ruleset and a tracked, time-boxed baseline of pre-existing violations, so the suite can go green while real debt is burned down deliberately rather than silently suppressed.

---

## 8. Prerequisite workstreams (before / alongside authoring specs)

1. **Live-app discovery pass.** This strategy was built from PRD + code reading only — the running app has **not** been driven yet. Before authoring, do a `playwright-cli` walkthrough of the golden path + each P0 area to validate real testid coverage, actual rendered flows vs. PRD, and any deviation (the working tree has WIP in `SubmissionContainer.tsx` and the Resend/SES email providers — email-delivery assertions target a moving part). This de-risks every later assumption.
2. **Seed-extension build (explicit workstream).** Extend `/dev/seed` (and/or add seed variants) to provide what UAT needs and the current seed lacks:
   - **RBAC admins** — one admin per non-SUPER sub-role (OPERATIONS/FINANCE/CONTENT_CREATOR/CONTENT_APPROVER) for the §6a boundary tests.
   - **Pagination/search/filter volume** — enough verifications/users/payouts to exercise the server-driven DataTable convention (the primary seed's two verifications can't paginate).
   - **Per-area fixture variants** — e.g. a PAID-but-unassigned verification, a COMPLETED report for re-check/dispute entry, a backdated entity for a specific time-window (§5 option 2).
   - Everything else stays **API-bootstrap helpers** in spec setup (§3 step 3); the seed covers the common/expensive baseline.
3. **Testid-coverage audit** across the 20 areas — enumerate missing `{flow}-{element}` anchors; gaps become a scoped frontend change list (frontend + backend contract stays in sync per CLAUDE.md).
4. **Trigger-endpoint reachability** — confirm admin sweep endpoints (`/admin/verifications/sweeps/*`, `/messages/sweeps/retries`) are callable in the automation env and whether any need a UI affordance vs. API-only.

### 8a. Suite longevity (keeping "green = accepted" trustworthy)

- **Flake policy.** Playwright `retries` (1–2 in the reporting run), a `@flaky` quarantine tag that keeps a known-unstable test visible but non-blocking until fixed, and engine-tagged triage (many failures are WebKit/Firefox-specific timing).
- **Determinism over sleeps.** Web-first assertions and explicit state waits (`__app_ready__`, DOM state) — never fixed `waitForTimeout`. For SSE live-update scenarios, confirm the **test-env poll interval** is short (the prod 60s fallback would make tests slow/flaky) — if it isn't configurable down, drive the change via API and assert after an explicit refresh rather than waiting on the poll.
- **Re-run idempotency.** `globalSetup` reset+seed makes each full run reproducible from a clean baseline; specs must not leak state a re-run depends on.
- **Artifacts.** Playwright HTML report + trace + screenshot + video on failure, retained to a known folder so a stakeholder can inspect any red without re-running.

---

## 9. How to run (local/manual)

1. Stack: `docker compose up -d postgres redis mailpit`; backend `APPODUS_ACTIVE_ENV=dev_personal` (or `test`), `OTP_MODE=deterministic`, `ENABLE_OUT_MESSAGING=True`, `EDGE_AUTH_SECRET` blank, `PAYMENT_STUB_MODE=True`; `alembic upgrade head`; `python veriprops.py` (`:8000`).
2. Frontend **over HTTPS**: `NEXT_PUBLIC_ENVIRONMENT=dev_personal pnpm dev:https` (`https://localhost:3000`) so hooks/testids are live.
   **TLS is mandatory, not cosmetic.** The session cookies are `__Host-` prefixed and therefore `Secure`. Chromium treats `http://localhost` as a secure context and keeps them; **WebKit does not** and silently drops all four, so over plain http every authenticated scenario fails on Safari for a reason that cannot occur in production (HTTPS behind Cloudflare). This was observed, not assumed: on http WebKit stored 0 cookies vs Chromium's 4; on https both store 4.
   First run needs a certificate — Next's `--experimental-https` auto-generation calls `mkcert -install`, which needs admin rights. Without elevation, generate one that is merely self-signed (Playwright sets `ignoreHTTPSErrors`, so it need not be CA-trusted):

   ```bash
   mkdir -p certificates && "$LOCALAPPDATA/mkcert/mkcert-v1.4.4-windows-amd64.exe" \
     -key-file certificates/localhost-key.pem -cert-file certificates/localhost.pem \
     localhost 127.0.0.1 ::1
   ```

   `certificates/` is gitignored and per-machine.
3. `pnpm e2e` (single worker) — `globalSetup` reset+seeds once; `--grep @P0` or `--grep UAT-PAY` to scope; `UAT_ENGINES=chromium-desktop` (or `--project=…`) to run one engine/device of the six-permutation matrix (§7). `UAT_BASE_URL` overrides the origin.
4. Debug failures with the Playwright trace viewer (`pnpm e2e:report`) and the `playwright-cli` skill for ad-hoc UI investigation.

## 10. Out of scope

- No CI wiring (`pull_requests.yml`/`e2e.yml`) — local/manual only for now.
- Load/performance and security **pen-testing** (the public-lookup rate-limit gap in PRD §G is a `security-review` item; UAT covers only *functional* authorization per §6a). Accessibility is **in scope** (§7), not deferred.
- Global PRD §G exclusions (live gateways/KYC/storage/FX/disbursement, offline upload, image derivatives, chat attachments, Legal Opinion flag-off, unbuilt `TODO(gap)` routes, all post-MVP) — asserted against stubs or skipped, never as real behaviour; launch-gate business/legal items flagged as go-live blockers, not UAT.

## 11. Validated against three in-repo sources of truth

- PRD §6–§25 (areas) + §G (exclusions).
- [frontend/src/lib/routes.ts](../frontend/src/lib/routes.ts) (`ROUTES`, built vs. `TODO(gap)`).
- [backend/scripts/e2e_drive_through.py](../backend/scripts/e2e_drive_through.py) 17-stage order — the ready-made linear-dependency map to mirror at the UI layer (API-level today, so this Playwright pass is net-new UI coverage, not duplication).


## 12. Implementation status

Built and verified green against a live local stack — **78/78 across the full six-permutation engine matrix** (Chromium/Firefox/WebKit × desktop/mobile), zero retries needed. Every scenario below is therefore *accepted* under §1's "green on all engines" rule.

**Foundation — [frontend/e2e/](../frontend/e2e/)**

| Piece | File | Notes |
| --- | --- | --- |
| Runner config + engine matrix | `playwright.config.ts` | Six projects (§7); `UAT_ENGINES` narrows for a local loop. Single worker, retries, trace/screenshot/video on failure. |
| One reset+seed + persona sessions | `global-setup.ts` | Seeds once, logs in 7 personas via the real login form, saves `storageState` + the run's seed payload. |
| API bootstrap client | `helpers/api.ts` | CSRF-aware, envelope-unwrapping; **preconditions only**, never assertions. |
| Readiness / auth hooks | `helpers/app.ts` | `waitReady`, `authSnapshot`, `expectAuthenticated` — no fixed timeouts anywhere. |
| UI login | `helpers/auth.ts` | The one place credentials are typed. |
| Mailpit | `helpers/mailpit.ts` | `waitForEmail`, `extractLinkFromEmail` (HTML **and** plain-text bodies). |
| Accessibility | `helpers/a11y.ts` | `expectNoA11yViolations` — WCAG 2.1 A/AA, serious+critical block, empty tracked baseline. |
| Seed accessors / personas | `helpers/seed.ts`, `helpers/personas.ts` | Credentials always come from the seed payload, never hardcoded. |

**Scenarios (13 green)**

| Area | Ids | PRD | Risk |
| --- | --- | --- | --- |
| Dev/QA contracts | `UAT-DEV-01…05` — seed shape, window hooks, deterministic OTP, Mailpit capture, captured session | §25 | P0 |
| Auth & Sessions | `UAT-AUTH-01…08` — route protection + redirect preservation, login a11y, wrong-password rejection, portal landing, password-reset round trip via Mailpit, guest-only bounce, devices surface + a11y, agent portal routing | §7 | P0 |

**Findings from the discovery pass (§8.1) — all resolved**

- **`__auth_snapshot__` was only published by the session *query*.** A freshly logged-in or restored session left the hook `null`, so automation could not observe auth on the paths users actually take. Fixed at the choke point: `publishAuthSnapshot` ([lib/automation.ts](../frontend/src/lib/automation.ts)) is now called from every `useAuthStore` session mutation **and** on rehydration; the duplicated inline write in `useAuthQueries` is gone. Unit-tested in `lib/automation.test.ts`.
- **Serious a11y violation (contrast 2.81:1, needs 4.5:1).** `text-brand-on-surface-variant/55` on 12px metadata text in devices, security, consent-history and activity-timeline. The `/55` alpha was removed in all four places (base token is ~9:1).
- **Missing testids** on the reset-password confirm field and submit button — added as `reset-password-confirm` / `reset-password-submit` and recorded in the frontend CLAUDE.md policy table.
- **WebKit dropped every session cookie over plain http** — 8 authenticated scenarios failed on WebKit desktop+mobile while Chromium and Firefox passed. Root cause is environmental, not an app defect: `__Host-`/`Secure` cookies are rejected by WebKit on an `http://localhost` origin. Fixed by running the suite over TLS (§9 step 2), which is also closer to production. No app code changed.

**Known limitations**

- **No CI wiring** (unchanged, §10) — local/manual runs.
- Firefox's mobile project is a phone-sized viewport only — Playwright has no touch/`isMobile` emulation for Gecko.
- The remaining 18 areas of §6, the §4 golden-path backbone, and the §8.2 seed extension (RBAC admins, pagination volume, fixture variants) are **not built yet**.

**Next**: the §4 golden-path backbone (it produces the shared ids the branch specs consume), then the §8.2 seed extension, then P0 areas — Submission & Payment, Review/Trust/Release, Public Lookup, Disputes, Earnings/Payouts, Audit/Erasure.

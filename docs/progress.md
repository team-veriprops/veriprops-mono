# Progress Tracker — Playwright UAT suite (cycle 3)

status: **Slice 0 passed. Slice 1 is partial.** All changes are uncommitted, pending user approval.

## Slice 0 — baseline gate (existing 5 specs × 6 projects)
- **Stack:** backend `dev_personal` on :8000. Frontend is the **production standalone build** (`node .next/standalone/server.js` on :3001) behind Caddy TLS on :3000 ([e2e/tls/Caddyfile](../frontend/e2e/tls/Caddyfile)). See uat-strategy §9.
- **chromium-desktop:** 24/24 on first attempt, after the fixes below.
- **Full matrix:** 144 tests (24 × 6 projects), **143 passed first attempt, 0 failed**, 1 retry, 23.3 min.
  - The retry was UAT-WAH-01 on chromium-mobile. Its setup POST `/dev/whatsapp/handoff-token` got a 502 because Caddy logged `dial tcp …:3001: i/o timeout` twice: Docker Desktop's container→host hop stalled. The request never reached Next or the backend, and the next mint (5 s later) succeeded.
  - Environment, not the app. Fix: the Caddyfile retries failed dials within 15 s (`lb_try_duration`, `dial_timeout 10s`); a failed dial was never sent, so this is safe for POST.
  - The matrix was **not re-run** after that Caddyfile change.
- **Every retry, and what caused it:**
  - **UAT-AUTH-05:** three causes, all fixed.
    - The spec logged in before the reset request had completed; it now waits for `?reset=ok`.
    - A wrong-password 401 triggered a session refresh, so login showed "Session refresh failed". `FetchHttpClient` now skips the refresh without a refresh cookie and surfaces the original error; UAT-AUTH-03 asserts the message via `login-error`.
    - Caddy reused an upstream socket Node had closed after its 5 s keep-alive, so the POST got a bare 502. The Caddyfile now sets `keepalive 2s`.
  - **UAT-DEV-02:** the home pricing section hydrated with a mismatch, because the server rendered static prices and the client the backend's. Prices are now fetched on the server via `lib/public-config.server.ts` and the shared `lib/backend-fetch.server.ts`; the static figures are deleted.
  - **UAT-GP-01:** `next dev` compiled the route on first visit. The suite now runs against the production build.
  - **UAT-WA-01:** the home page's `load` event waited on Google Fonts and a Google-hosted hero image.
    - Fonts are self-hosted via `next/font` (`lib/fonts.ts`).
    - The hero image is committed at `public/assets/hero-property.png` and preloaded via `next/image`.
    - `goto()` waits for `domcontentloaded`, then `__app_ready__`.
- **SEO pass (user requirement: every UI decision is SEO-optimized):**
  - The pricing tiers now carry `pricingJsonLd` (a schema.org Service with one NGN Offer per priced tier), built from `withLivePrices`, the same helper the pricing section renders from.
  - Verified in the served HTML: backend prices, 3 Offers, no third-party font/image hosts, font and hero preloads.
- **Gates:** Vitest 593/593, `tsc` and eslint clean. Backend unit 2066/2066 (`/dev/scenario` work); ruff and mypy clean.

## Slice 1 — foundation (partial, uncommitted)
- **Done:** `POST /dev/scenario` (`dev/scenario.py`, `dev/fixtures.py`, e2e `helpers/scenario.ts`) builds stages `DRAFT` → `RELEASED` on both tiers. Live-verified 11/11.
- **Remaining:**
  - `DISPUTED`/`RECHECK_REQUESTED`/`PAYOUT_READY` stages; the seed extension (RBAC admins, extra verifications); `e2e/fixtures.ts`; `helpers/ui.ts`; parallel config; `DataTable`/`DetailDrawer` testids.
  - `buildScenario` has no consumer yet.

---

# Progress Tracker — WhatsApp Channel (cycle 2)

status: **cycle complete** — S1–S11 delivered (+ S4.1 template registry, + S10.0 handoffs)

## Completed Slices
- S1 widget + attribution (dc7adb4)
- S2 channel foundation (webhook + facade + console inbound)
- S3 handoff tokens + /wa/* landings
- S4 OTP account linking (E1) + number lifecycle
- S4.1 §26.7 Meta template registry + S4 follow-up defects
- S5 bot engine core (intent facade, guardrails, status flow, admin console mode + hand-back)
- S6 resumable chat intake + payment handoff (586de9c)
- S7 console outbound adapter (WA-12/WA-41) + Meta's 24-hour window + §26.6.3 non-text policy
  (WA-06/WA-38) (3c53bd2)
- S8 dual consent (WA-27), event-driven milestones (WA-16/WA-34), report delivery (WA-35)
- S9 slim per-case delegates (WA-26) (72ef8a9)
- **S10.0 reachable pay/report handoffs (WA-17)** — unplanned; §26.3.4 marks three actions
  `HANDOFF` and only `upload` had a producer, so `/wa/pay/<token>` and `/wa/report/<token>`
  were built, tested and unreachable from a conversation (be32c7a)
- **S10 channel analytics (WA-43)** (634d0ef)
- **S11 live hardening & launch-gate closeout (WA-40, WA-42, WA-44; WA-02 code-side)**
- **S12 closeout pass** — the §26 incorporation plus the loose ends S11 left:
  - PRD.md's standalone §7 spec folded into **MASTER-PRD §26** (subsections 26.1–26.11), and
    every `§7.x` reference in the repo resolved. `§7.x` had meant *three* things at once —
    MASTER-PRD §7 (Auth), the legacy v2.4 Phase 7 (Agent Task Execution, now §11.3/§11.4/§12.x),
    and the channel — so ~1,420 references across 268 files were disambiguated, not just
    renamed. §G gained the WhatsApp rows, including the `google_drive` marker that had been
    unpaired since D83.
  - **A stale consent literal in both e2e harnesses.** Migration 0011 moved PLATFORM_TERMS and
    PRIVACY_POLICY to `1.1.0`; the harness still signed `1.0.0`, so every drive-through customer
    was created already owing the two consents it had just accepted. Versions now come from
    `GET /users/auth/consents/documents`, and each signup asserts it owes nothing afterwards.
  - **§26.8 compliance is now proven live, not just mocked** — the consent ledger exporting in
    the §19.3 pack, erasure reaching the five channel tables, and the erased number reading as a
    stranger to the bot on its next message. 470 checks, up from 445.
  - Defect fixes: a bare `raise` in the callback service that threw `RuntimeError: No active
    exception to reraise` instead of a 404; two silently-swallowed `AttributeError`s; dead
    commented-out blocks. The unreachable frontend upload cluster (mock service, offline queue,
    six `ui/upload` components and an unregistered service worker) was deleted.

## Current Slice
- none

## Pending Slices
- none — the cycle's code-side scope is complete. What remains is external (§26.11 hard gates)
  and is tracked in [whatsapp-launch-runbook.md](whatsapp-launch-runbook.md).

## Runtime State
- idle (checkpointed after S11)

## Pending Recovery
- none

## Blockers
- none in code. Launch is gated on the external §26.11 items — Meta business verification,
  template approval, number custody, counsel sign-off on retention duration.

## Findings outside the WhatsApp scope
- `appodus_utils/domain/webhook/google_drive/` is **dead and does not import**: `repo.py`,
  `service.py` and `validator.py` reference `main.app.domain.webhook.google_drive.*` and
  `main.app.db.repo`, neither of which exists, so only `model.py` loads — and it registers a
  `g_drive_webhook_subscriptions` table with no migration builder. Nothing in the app's import
  graph reaches it, so it is inert rather than broken in production.
  **Resolved as D83 (2026-09-03): kept and marked**, not deleted — it is vendored code outside
  this cycle's scope. The greppable `TODO(gap):` is on `model.py`, and its paired
  "Known Gaps & Roadmap" row landed with the §26 incorporation (MASTER-PRD §G.2), so
  `grep -rn "TODO(gap)"` enumerates every deferred item again.

## Open Questions
- none (gate decisions D42–D48; run-time decisions D49–D86)

## What later work should know
- **All seven §26.7 templates have senders**, and all three §26.3.4 `HANDOFF` actions now have
  producers. What remains external is Meta's **approval** of each template, which the admin
  registry displays and which deliberately never blocks a send — a stale sync must not take the
  channel down. Confirm at the live smoke that the approved `otp_auth` button matches the shape
  we send.
- The §26.4.4 SMS fallback is wired (D60, amending D46): a failed WhatsApp send falls back to SMS
  on the same number through the router's existing Termii → Twilio chain.
- Migrations 0002–0011 are applied and round-tripped against live Postgres.
- **The §26.3.2 projection now has three consumers**: the status flow, §26.6.3's uploadable-case
  filter, and S10.0's pay/report eligibility. The last one is the subtle case —
  `ChannelState.REPORT_READY` projects from `UNDER_REVIEW`, where the report exists but has not
  passed the §8 release gate, so only `DELIVERED` may be offered a report link.
- §26.4.6's **marketing** consent is captured and stored from day one but gates nothing: there
  are no marketing templates at v1 (P1 drafts them only when a campaign exists). §26.10 now
  reports its opt-in rate, which is the number that says how big a Marketplace launch audience
  would be (D84).
- §26.9's delegate enhancements (multiple delegates, granular permissions) are untouched by
  design — `GET /verifications/{id}/delegates` already returns a list, so the shape survives.
- **Deploying the §26.8 copy asks every existing account to re-accept.** The three documents move
  to consent version `1.1.0`, which is the correct NDPA answer for a new cross-border transfer
  disclosure and a visible UX event on the day. Retention *duration* is still counsel's call, so
  the clauses name the policy rather than a number and all three stay `DRAFT`.

## Launch-gate checklist (§26.11)
Full runbook, with owners and order: [whatsapp-launch-runbook.md](whatsapp-launch-runbook.md).
The one-way step (concierge → Cloud API number binding) is called out there.

- [ ] ⊘ Meta Business verification approved; green tick granted
- [~] All §26.7 templates approved — all 7 declared, bodied, **sent by real code paths**, and
      visible in the admin registry with Meta-synced status; submission and approval external
- [ ] ⊘ Number custody confirmed and documented (+2349167624347)
- [x] Fraud-scan pipeline verified against WhatsApp-sourced messages (drive-through evidence)
- [~] Token pen-check — automated coverage green; the human/proxy items remain
      (docs/handoff-token-pen-check.md)
- [x] Failure fallback **tested**, not just implemented — `POST /dev/whatsapp/fail-next-turn`
      makes one real turn fail and the drive-through asserts the §26.6.5 apology, the human
      promise in whichever shape Decision G's coverage gives, the `BOT_PIPELINE_FAILED` admin
      alert, the one-shot reset, and the §26.10 `PIPELINE_FAILURE` count
- [~] ToS + privacy policy updated per §26.8 — clauses live at consent version `1.1.0`;
      counsel sign-off on **retention duration** outstanding, and the documents stay `DRAFT`
      until it lands
- [ ] ⊘ Console rota covering G1 hours (must match `support_hours_*` in `system_config` — the
      bot quotes those numbers to customers)
- [ ] ⊘ Concierge → Cloud API cutover scheduled (number binding is one-way)
- [ ] ⊘ Conversation-theme tracker live from first concierge chat

## Risks
- Meta platform dependency (accepted, §26.11). Early warning is now instrumented: §26.10 reports
  the quality rating with its sync age, and `YELLOW` is the signal to slow template volume.
- Template-approval lag (mitigation: the registry shipped early, in S4.1).
- Live-path external assets (D43 fallback: the stub keeps everything demoable, and
  `ENVIRONMENT=prod` refuses to boot on it).

## Last Commit
- S11: live-path hardening and launch-gate closeout

## Completion %
- 100 of the cycle's code-side scope (11 of 11 slices, plus S4.1 and S10.0).
  42 of 44 requirements complete; WA-02 and WA-41 are `partial` **only** on external Meta items.

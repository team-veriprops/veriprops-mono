# Progress Tracker

status: running (S1–S4 foundation)

## Completed Slices
- S1  Foundation reconciliation & doc fixes — cleaned 0001 orphaned seeds (pricing + trust-weights),
      moved `app/state` → `app/core/state`, root CLAUDE.md MySQL→PostgreSQL, removed 9 orphaned
      deleted-domain tests → suite green (267 passed).
- S2  State derivation owner + task-dependency config — `app/core/state/{status,derive,dependencies}.py`;
      pure `derive_status` (§2.5) + tier composition / Lawyer-dependency / acyclicity (§4.2). 49 tests, 316 total.
- S3  Idempotency + VID + evidence-hash — `app/core/vid.py`, `app/core/evidence.py`,
      `app/core/idempotency/{models,repo,service}.py`; `idempotency_keys` table folded into 0001;
      Money kobo-reconciliation tests. 344 total. (Live `alembic upgrade head` deferred — no DB here.)
- S4  SLA business-day calculator + Nigerian holiday calendar — `app/core/sla.py` (fixed + Easter-computus
      + maintained movable-Islamic holidays; per-tier due dates 5/7/10). 363 total.
- S5  Phase 1 — Marketing completion + Legal documents + footer pages.
      Backend: `consent_documents` gains `body` + `signoff_status` (0001); legal content registry
      (`consent/content/`, 10 drafted docs from PRD §3.5); idempotent `ConsentService.seed_documents()` wired
      into `DataSeeder`; public read API (`GET /consents/documents`, `/documents/{slug}`). Frontend: reusable
      SEO pattern (`lib/seo.ts buildMetadata` + `JsonLd`) applied to all public pages, `app/sitemap.ts` +
      `app/robots.ts`; dynamic `/legal/[slug]` pages (react-markdown) with DRAFT banner; conversion FAQ after
      Client Stories (FAQPage JSON-LD); `/sample-report`; footer dynamic year + socials disable-when-unset.
      Backend 373 tests; frontend +seo/home.data tests (58). Live-verified: API returns 10 docs, DRAFT/FINAL
      correct, legal pages + sitemap/robots render. Incidental baseline build repairs (not mine): added
      `NotificationBell` stub (AppShell orphan import), removed dead `lib/mockUrlExtractor.ts`.

## Current Slice
- S6 (Phase 2 auth hardening) — pending start.

## Pending Slices
- S6  Phase 2 — Auth hardening
- S7  Phase 3 — Agent onboarding & KYC
- S8  Phase 4 — Admin onboarding & RBAC
- S9  Phase 5 — Customer submission & payment  *(gated: liability-cap copy §B)*
- S10 Phase 6 + 6a — Admin control panel & chargeback
- S11 Phase 7 — Agent task execution
- S12 Phase 8 — Admin review & report release
- S13 Phase 9 — Customer tracking & evidence (SSE)
- S14 Phase 10 — Final report experience  *(gated: NBA sign-off for Legal Opinion go-live §B)*
- S15–S23 Phases 11–19 — harden & scale

## Runtime State
- idle (S1–S4 committed; checkpoint clean)

## Pending Recovery
- none

## Blockers
- none. Migration validated live on the test DB (`downgrade base` + `upgrade head` clean; `idempotency_keys`
  created with correct columns/indexes). Pre-squash orphan tables (`pricing_tier_configs`,
  `trust_score_weight_config`) remain in the test DB — no current migration creates them; recreated in S9/S12.

## Open Questions
- D6 (relaxed by D9): foundation built greenfield; `0001` is the single editable initial migration.
- D4: applied in S1 — root CLAUDE.md now says PostgreSQL.
- §B legal sign-offs are launch gates, not build blockers: liability-cap copy gates Phase 5 go-live;
  NBA counsel gates Phase 10 Legal Opinion go-live; Premium-lawyer insurance posture gates that tier.
- §6.4 admin staffing gate is a business commitment (not buildable) — record before launch.

## Risks
- State-derivation correctness (single owner, tier-config counts) — highest-leverage correctness risk.
- Money/FX reconciliation to the kobo across pay→refund→commission→payout.
- Webhook double-processing (mitigated by idempotency keys, proven in S3).
- Brownfield drift between rebuilt models and `0001` schema.
- Strict commit mode + dirty worktree: `run` is blocked until committed (see below).

## Last Commit
- S1 `bec85e1`, S2 `0465a5a`, S3 `a138219`, S4 (this commit) — foundation slices.

## Completion %
- ~17% (4 of 23 slices; all Phase-0 foundation primitives complete)

---

### ⚠️ Strict-mode reminder
`config.yaml` is `mode: strict` (D3). Worktree committed at each slice boundary; clean between slices.

<!-- legacy note retained for history -->
`config.yaml` is `mode: strict` (D3). The worktree was previously **dirty** (large staged domain deletions +
edits). `prd-orchestrator run` will refuse to start until the worktree is committed/clean. Commit the in-flight
refactor before invoking `run`.

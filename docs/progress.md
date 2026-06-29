# Progress Tracker

status: initialized

## Completed Slices
- none

## Current Slice
- none

## Pending Slices
- S1  Foundation reconciliation & doc fixes
- S2  State-machine core (validator + derivation owner + dependency config)
- S3  Money / idempotency / VID / evidence-hash primitives
- S4  SLA business-day & Nigerian holiday calendar
- S5  Phase 1 — Marketing completion
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
- idle

## Pending Recovery
- none

## Blockers
- none (build can begin at S1)

## Open Questions
- D6: rebuilt domain models must reconcile to the existing `0001` schema (treat `0001` as the contract).
- D4: CLAUDE.md says MySQL; code+PRD say PostgreSQL — correction flagged, to apply in S1.
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
- none (initialize writes docs only; no source changes)

## Completion %
- 0

---

### ⚠️ Strict-mode reminder
`config.yaml` is `mode: strict` (D3). The worktree is currently **dirty** (large staged domain deletions +
edits). `prd-orchestrator run` will refuse to start until the worktree is committed/clean. Commit the in-flight
refactor before invoking `run`.

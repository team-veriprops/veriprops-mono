# Progress Tracker — WhatsApp Channel (cycle 2)

status: in progress — S1–S9 complete (+ S4.1 template registry)

## Completed Slices
- S1 widget + attribution (dc7adb4)
- S2 channel foundation (webhook + facade + console inbound)
- S3 handoff tokens + /wa/* landings
- S4 OTP account linking (E1) + number lifecycle
- S4.1 §7.7 Meta template registry + S4 follow-up defects
- S5 bot engine core (intent facade, guardrails, status flow, admin console mode + hand-back)
- S6 resumable chat intake + payment handoff (586de9c)
- S7 console outbound adapter (WA-12/WA-41) + Meta's 24-hour window + §7.6.3 non-text policy
  (WA-06/WA-38) (3c53bd2)
- S8 dual consent (WA-27), event-driven milestones (WA-16/WA-34), report delivery (WA-35)
- S9 slim per-case delegates (WA-26)

## Current Slice
- none — S10 is next

## Pending Slices
- S10 channel analytics
- S11 live hardening & launch-gate closeout

## Runtime State
- idle (checkpointed after S9)

## Pending Recovery
- none

## Blockers
- none (S11 live path awaits external Meta assets — tracked, not blocking S1–S10)

## Findings outside the WhatsApp scope (not fixed — awaiting a call)
- `appodus_utils/domain/webhook/google_drive/` is **dead and broken**: its `repo.py`,
  `service.py` and `validator.py` import `main.app.domain.webhook.google_drive.*` and
  `main.app.db.repo`, neither of which exists, so only `model.py` imports cleanly — and it
  registers a `g_drive_webhook_subscriptions` table that has no migration builder. Nothing
  in the app's import graph reaches it, so it is inert rather than broken-in-production,
  and the orphan guard never saw it. Surfaced while building the decorated-service guard.
  It is vendored code outside the WhatsApp scope, so it is reported rather than deleted:
  the choice is to remove the package or to wire it up and give it a migration.

## Open Questions
- none (gate decisions D42–D48; run-time decisions D49–D79)

## Carried into later slices
- **All seven §7.7 templates now have senders.** `otp_auth` (S4), `window_reopen` (S7), the
  four milestones (S8) and `delegate_status` (S9). What remains external is Meta's
  **approval** of each, which the admin registry displays and which deliberately never
  blocks a send — a stale sync must not take the channel down. Still to confirm at the S11
  live smoke: that the approved `otp_auth` button matches the shape we send.
- The §7.4.4 SMS fallback is wired (D60, amending D46): a failed WhatsApp send falls back
  to SMS on the same number through the router's existing Termii → Twilio chain.
- Migrations 0002–0009 are applied and verified against live Postgres; the UAT suite is
  green on chromium-desktop (24/24). The remaining five engines have not been run.
- The §7.3.2 channel-state projection (`bot/projection.py`) is built and unit-tested over
  every `VerificationStatus`, but nothing reads it yet — S10's analytics is its consumer.
- §7.4.6's **marketing** consent is captured and stored from day one but gates nothing:
  there are no marketing templates at v1 (P1 drafts them only when a campaign exists). The
  state is collected now because an opt-in asked for later is an opt-in mostly not given.
- S9 leaves §7.9's delegate enhancements (multiple delegates, granular permissions) alone
  by design — the `GET /verifications/{id}/delegates` contract already returns a list, so
  the shape survives that change without a break.

## Launch-gate checklist (§7.11 — external/business items, mirrored from PRD)
- [ ] Meta Business verification approved; green tick granted
- [~] All §7.7 templates approved — all 7 declared, bodied, **sent by real code paths**, and
      visible in the admin registry (`/admin/config/whatsapp-templates`) with Meta-synced
      status; submission and approval remain external
- [ ] Number custody confirmed and documented (+2349167624347)
- [ ] Fraud-scan pipeline verified against WhatsApp-sourced messages (S2 test evidence)
- [~] Token service pen-checked (S3/S11) — automated coverage landed + checklist drafted
      (docs/handoff-token-pen-check.md); the human/proxy items remain
- [~] Failure fallback tested — §7.6.5 is implemented and unit-tested (any bot exception
      becomes a warm handover + a `BOT_PIPELINE_FAILED` admin notification); the live drill
      against a real classifier outage belongs to S11
- [ ] ToS + privacy policy updated per §7.8 (counsel: chat-log retention duration).
      **S8 note:** the consent record the policy has to describe now exists and is
      exportable — `whatsapp_consents` keeps a grant/revoke timestamp pair plus the capture
      point for each of the two opt-ins.
- [ ] Console rota covering G1 hours
- [ ] Concierge → Cloud API cutover scheduled (number binding is one-way)
- [ ] Conversation-theme tracker live from first concierge chat

## Risks
- Meta platform dependency (accepted, §7.11); template-approval lag (mitigation: S8 registry early);
  live-path external assets (D43 fallback: stub keeps everything demoable).

## Last Commit
- S9: slim per-case delegates with status-only visibility

## Completion %
- ~82 (9 of 11 slices, plus the §7.7 registry from S8 delivered early in S4.1)

# Progress Tracker — WhatsApp Channel (cycle 2)

status: in progress — S1–S5 complete (+ S4.1 template registry)

## Completed Slices
- S1 widget + attribution (dc7adb4)
- S2 channel foundation (webhook + facade + console inbound)
- S3 handoff tokens + /wa/* landings
- S4 OTP account linking (E1) + number lifecycle
- S4.1 §7.7 Meta template registry + S4 follow-up defects
- S5 bot engine core (intent facade, guardrails, status flow, admin console mode + hand-back)

## Current Slice
- none — S6 is next

## Pending Slices
- S6 intake flow + payment handoff + continuation
- S7 console adapter completion
- S8 consent + milestones + report delivery (template registry landed in S4.1)
- S9 delegates (O2)
- S10 channel analytics
- S11 live hardening & launch-gate closeout

## Runtime State
- idle (checkpointed after S5)

## Pending Recovery
- none

## Blockers
- none (S11 live path awaits external Meta assets — tracked, not blocking S1–S10)

## Known gap between S5/S6 and S7 — close this first in S7
- **An agent's reply in the WhatsApp console is stored but never delivered.** S5 added the
  `/admin/messages` WhatsApp tab (needed, because D57's hand-back had to ship with the rule
  that makes a thread sticky), and it renders a composer. `CommunicationService.post_message`
  writes the message into the thread and flips the session to `HUMAN`, but nothing fans it
  back out over WhatsApp — the plan assigns that to S7, so between these commits an agent can
  type a reply the customer never receives. S7's first task: fan an admin reply on a
  `channel=WHATSAPP` thread out through the transport, gated by `WhatsAppWindowService.is_open`
  (free text inside Meta's window, the `window_reopen` §7.7 template outside it).

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
- none (gate decisions D42–D48; run-time decisions D49–D58)

## Carried into later slices
- Meta **template** sends are wired (D59/D61): all seven §7.7 templates are declared with
  bodies, `otp_auth` sends as a template with its mandatory OTP button, and the admin
  registry syncs approval status. Still to confirm at the S11 live smoke: that the
  approved template's button matches the shape we send — a mismatch to correct, not an
  unimplemented requirement.
- The §7.4.4 SMS fallback is wired (D60, amending D46): a failed WhatsApp send falls back
  to SMS on the same number through the router's existing Termii → Twilio chain.
- Six of the seven templates have no sender yet: milestones + report delivery land in S8,
  `window_reopen` in S7 (`WhatsAppWindowService` is already in place), `delegate_status`
  in S9.
- Migrations 0002/0003 are applied and verified against live Postgres; the UAT suite is
  green on chromium-desktop (24/24). The remaining five engines have not been run.
- S7 owns the rest of the outbound console: Meta's 24-hour window on an agent's late reply
  (`window_reopen`), and the richer §7.6.3 media handling. S5 landed the agent-reply path
  (`/admin/messages` → WhatsApp tab, posting through the generic conversation endpoint) and
  the bot's own §7.6.3 answer — a voice note, pin or contact card is acknowledged and handed
  to a person rather than journalled in silence.
- S5 deferred two things it names honestly rather than fakes: `START_VERIFICATION` escalates
  to a human (`CAPABILITY_NOT_OFFERED`) until S6 builds the intake flow, and `LINK_ACCOUNT`
  points at S4's linking rather than driving it. Both are `TODO(gap):`-free because they are
  scheduled slices, not gaps.
- The §7.3.2 channel-state projection (`bot/projection.py`) is built and unit-tested over
  every `VerificationStatus`, but nothing reads it yet — S10's analytics is its consumer.

## Launch-gate checklist (§7.11 — external/business items, mirrored from PRD)
- [ ] Meta Business verification approved; green tick granted
- [~] All §7.7 templates approved — all 7 declared with bodies and visible in the admin
      registry (`/admin/config/whatsapp-templates`) with Meta-synced status; submission
      and approval remain external
- [ ] Number custody confirmed and documented (+2349167624347)
- [ ] Fraud-scan pipeline verified against WhatsApp-sourced messages (S2 test evidence)
- [~] Token service pen-checked (S3/S11) — automated coverage landed + checklist drafted
      (docs/handoff-token-pen-check.md); the human/proxy items remain
- [~] Failure fallback tested — §7.6.5 is implemented and unit-tested (any bot exception
      becomes a warm handover + a `BOT_PIPELINE_FAILED` admin notification); the live drill
      against a real classifier outage belongs to S11
- [ ] ToS + privacy policy updated per §7.8 (counsel: chat-log retention duration)
- [ ] Console rota covering G1 hours
- [ ] Concierge → Cloud API cutover scheduled (number binding is one-way)
- [ ] Conversation-theme tracker live from first concierge chat

## Risks
- Meta platform dependency (accepted, §7.11); template-approval lag (mitigation: S8 registry early);
  live-path external assets (D43 fallback: stub keeps everything demoable).

## Last Commit
- S4.1: Meta template registry (§7.7) + S4 follow-up defects

## Completion %
- ~38 (4 of 11 slices, plus the §7.7 registry from S8)

# Progress Tracker — WhatsApp Channel (cycle 2)

status: **cycle complete** — S1–S11 delivered (+ S4.1 template registry, + S10.0 handoffs)

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
- S9 slim per-case delegates (WA-26) (72ef8a9)
- **S10.0 reachable pay/report handoffs (WA-17)** — unplanned; §7.3.4 marks three actions
  `HANDOFF` and only `upload` had a producer, so `/wa/pay/<token>` and `/wa/report/<token>`
  were built, tested and unreachable from a conversation (be32c7a)
- **S10 channel analytics (WA-43)** (634d0ef)
- **S11 live hardening & launch-gate closeout (WA-40, WA-42, WA-44; WA-02 code-side)**

## Current Slice
- none

## Pending Slices
- none — the cycle's code-side scope is complete. What remains is external (§7.11 hard gates)
  and is tracked in [whatsapp-launch-runbook.md](whatsapp-launch-runbook.md).

## Runtime State
- idle (checkpointed after S11)

## Pending Recovery
- none

## Blockers
- none in code. Launch is gated on the external §7.11 items — Meta business verification,
  template approval, number custody, counsel sign-off on retention duration.

## Findings outside the WhatsApp scope
- `appodus_utils/domain/webhook/google_drive/` is **dead and does not import**: `repo.py`,
  `service.py` and `validator.py` reference `main.app.domain.webhook.google_drive.*` and
  `main.app.db.repo`, neither of which exists, so only `model.py` loads — and it registers a
  `g_drive_webhook_subscriptions` table with no migration builder. Nothing in the app's import
  graph reaches it, so it is inert rather than broken in production.
  **Resolved as D83 (2026-09-03): kept and marked**, not deleted — it is vendored code outside
  this cycle's scope. The greppable `TODO(gap):` is on `model.py`; the paired
  "Known Gaps & Roadmap" row lands with the MASTER-PRD §7 incorporation.

## Open Questions
- none (gate decisions D42–D48; run-time decisions D49–D86)

## What later work should know
- **All seven §7.7 templates have senders**, and all three §7.3.4 `HANDOFF` actions now have
  producers. What remains external is Meta's **approval** of each template, which the admin
  registry displays and which deliberately never blocks a send — a stale sync must not take the
  channel down. Confirm at the live smoke that the approved `otp_auth` button matches the shape
  we send.
- The §7.4.4 SMS fallback is wired (D60, amending D46): a failed WhatsApp send falls back to SMS
  on the same number through the router's existing Termii → Twilio chain.
- Migrations 0002–0011 are applied and round-tripped against live Postgres.
- **The §7.3.2 projection now has three consumers**: the status flow, §7.6.3's uploadable-case
  filter, and S10.0's pay/report eligibility. The last one is the subtle case —
  `ChannelState.REPORT_READY` projects from `UNDER_REVIEW`, where the report exists but has not
  passed the §8 release gate, so only `DELIVERED` may be offered a report link.
- §7.4.6's **marketing** consent is captured and stored from day one but gates nothing: there
  are no marketing templates at v1 (P1 drafts them only when a campaign exists). §7.10 now
  reports its opt-in rate, which is the number that says how big a Marketplace launch audience
  would be (D84).
- §7.9's delegate enhancements (multiple delegates, granular permissions) are untouched by
  design — `GET /verifications/{id}/delegates` already returns a list, so the shape survives.
- **Deploying the §7.8 copy asks every existing account to re-accept.** The three documents move
  to consent version `1.1.0`, which is the correct NDPA answer for a new cross-border transfer
  disclosure and a visible UX event on the day. Retention *duration* is still counsel's call, so
  the clauses name the policy rather than a number and all three stay `DRAFT`.

## Launch-gate checklist (§7.11)
Full runbook, with owners and order: [whatsapp-launch-runbook.md](whatsapp-launch-runbook.md).
The one-way step (concierge → Cloud API number binding) is called out there.

- [ ] ⊘ Meta Business verification approved; green tick granted
- [~] All §7.7 templates approved — all 7 declared, bodied, **sent by real code paths**, and
      visible in the admin registry with Meta-synced status; submission and approval external
- [ ] ⊘ Number custody confirmed and documented (+2349167624347)
- [x] Fraud-scan pipeline verified against WhatsApp-sourced messages (drive-through evidence)
- [~] Token pen-check — automated coverage green; the human/proxy items remain
      (docs/handoff-token-pen-check.md)
- [x] Failure fallback **tested**, not just implemented — `POST /dev/whatsapp/fail-next-turn`
      makes one real turn fail and the drive-through asserts the §7.6.5 apology, the human
      promise in whichever shape Decision G's coverage gives, the `BOT_PIPELINE_FAILED` admin
      alert, the one-shot reset, and the §7.10 `PIPELINE_FAILURE` count
- [~] ToS + privacy policy updated per §7.8 — clauses live at consent version `1.1.0`;
      counsel sign-off on **retention duration** outstanding, and the documents stay `DRAFT`
      until it lands
- [ ] ⊘ Console rota covering G1 hours (must match `support_hours_*` in `system_config` — the
      bot quotes those numbers to customers)
- [ ] ⊘ Concierge → Cloud API cutover scheduled (number binding is one-way)
- [ ] ⊘ Conversation-theme tracker live from first concierge chat

## Risks
- Meta platform dependency (accepted, §7.11). Early warning is now instrumented: §7.10 reports
  the quality rating with its sync age, and `YELLOW` is the signal to slow template volume.
- Template-approval lag (mitigation: the registry shipped early, in S4.1).
- Live-path external assets (D43 fallback: the stub keeps everything demoable, and
  `ENVIRONMENT=prod` refuses to boot on it).

## Last Commit
- S11: live-path hardening and launch-gate closeout

## Completion %
- 100 of the cycle's code-side scope (11 of 11 slices, plus S4.1 and S10.0).
  42 of 44 requirements complete; WA-02 and WA-41 are `partial` **only** on external Meta items.

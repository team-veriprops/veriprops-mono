# Progress Tracker — WhatsApp Channel (cycle 2)

status: in progress — S1–S3 complete

## Completed Slices
- S1 widget + attribution (dc7adb4)
- S2 channel foundation (webhook + facade + console inbound)
- S3 handoff tokens + /wa/* landings

## Current Slice
- none — S4 is next

## Pending Slices
- S4 OTP account linking (E1)
- S5 bot engine core
- S6 intake flow + payment handoff + continuation
- S7 console adapter completion
- S8 templates + consent + milestones + report delivery
- S9 delegates (O2)
- S10 channel analytics
- S11 live hardening & launch-gate closeout

## Runtime State
- idle (checkpointed after S3)

## Pending Recovery
- none

## Blockers
- none (S11 live path awaits external Meta assets — tracked, not blocking S1–S10)

## Open Questions
- none (gate decisions D42–D48; run-time decisions D49–D52)

## Carried into later slices
- Migration 0002/0003 verified by offline SQL generation only — no database was running
  locally. Apply and re-run the drive-through before relying on them.
- S7 owns the outbound half of the console: agent replies, Meta's 24-hour window, and the
  §7.6.3 policy replies for non-text inbound. S2 journals and labels non-text; it does not
  answer it.

## Launch-gate checklist (§7.11 — external/business items, mirrored from PRD)
- [ ] Meta Business verification approved; green tick granted
- [ ] All §7.7 templates approved
- [ ] Number custody confirmed and documented (+2349167624347)
- [ ] Fraud-scan pipeline verified against WhatsApp-sourced messages (S2 test evidence)
- [~] Token service pen-checked (S3/S11) — automated coverage landed + checklist drafted
      (docs/handoff-token-pen-check.md); the human/proxy items remain
- [ ] Failure fallback tested (S5/S11 drill)
- [ ] ToS + privacy policy updated per §7.8 (counsel: chat-log retention duration)
- [ ] Console rota covering G1 hours
- [ ] Concierge → Cloud API cutover scheduled (number binding is one-way)
- [ ] Conversation-theme tracker live from first concierge chat

## Risks
- Meta platform dependency (accepted, §7.11); template-approval lag (mitigation: S8 registry early);
  live-path external assets (D43 fallback: stub keeps everything demoable).

## Last Commit
- S3: RS256 handoff tokens + /wa landings

## Completion %
- ~27 (3 of 11 slices)

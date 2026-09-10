# PRD Analysis — WhatsApp Channel (PRD.md §26, cycle 2)

> Cycle 2 of the orchestrator. Cycle 1 (core platform) is archived in `docs.back/`; its as-built
> consolidation is [MASTER-PRD.md](../MASTER-PRD.md) (v3.0). This cycle implements the locked
> **§26 WhatsApp Channel (Verify)** spec in [PRD.md](../PRD.md) — Decision Record A–P, scope frozen.

## Executive Summary

WhatsApp becomes the **conversational front door** to the existing Verify product; veriprops.ng
remains the **vault** (all payments, documents, reports). One canonical backend serves both
surfaces — WhatsApp is a thin client over the same APIs the web dashboard uses. The build adds:
an inbound webhook receiver + facade over Meta Cloud API, a guardrailed bot engine, single-use
handoff tokens into the web app, OTP cross-channel identity linking, console-mediated human chat,
opt-in milestone templates, slim delegates, and channel analytics.

**Reuse position is strong.** Cycle 1 already ships: a live-send WhatsApp Business provider
(`backend/main/appodus_utils/integrations/messaging/providers/whatsapp/whatsapp_business.py`,
Cloud API v22 settings incl. `WHATSAPP_APP_SECRET_KEY` / webhook verify token / WABA ids in
`app/config/settings.py`), WhatsApp message models (templates, interactive buttons/lists) in
`appodus_utils/integrations/messaging/models.py`, the admin chat console + SSE fraud-scan pipeline
(§16), the event bus + notification router (§4.8/§17), OTP infra with the `OTP_MODE` determinism
contract, the consent domain, and the facade/stub pattern (§4.13).

## Goals

- Full §26.6 bot scope (frozen): welcome, FAQ/pricing, intake, payment handoff, status, milestones,
  report delivery, human escalation, refund routing, non-text handling, guardrails, failure fallback.
- Website side: chat widget (§26.4.1), `/wa/{pay,upload,report}/<token>` landing endpoints (§26.4.2),
  continuation affordances (§26.4.3), OTP linking (§26.4.4), delegate management (§26.4.5),
  dual consent capture (§26.4.6).
- Token service per §26.5 (RS256, 15-min, single-use jti, intent+case scoped).
- Template registry (§26.7), compliance surface updates (§26.8), analytics (§26.10).
- Live Meta Cloud API wiring from day one (user decision D43) with a deterministic stub sibling.

## Non-Goals (v1.1 backlog, §26.9 — frozen out)

- Voice-note transcription-assist (v1: route to human, flagged audio).
- Multiple delegates / granular delegate permissions.
- Pidgin or any non-English language.
- In-chat payment of any kind.
- Marketing template sends (consent capture only; no campaigns).

## Dependency Graph

```
S1 widget ──────────────────────────────┐ (independent, ships first)
S2 channel foundation (webhook+facade+console inbound)
   ├─→ S5 bot engine core (welcome/FAQ/status/escalation/failure)
   │      ├─→ S6 intake flow ──→ S8 consent+templates+milestones
   │      └─→ S7 console adapter full (replies out, fraud scan, non-text)
   ├─→ S3 token service + /wa/* landings ──→ S6 (payment handoff), S8 (report delivery)
   └─→ S4 OTP linking (E1) ──→ S5 status flow, S9 delegates
S8 ──→ S9 delegates (delegate_status template) ──→ S10 analytics ──→ S11 live hardening/launch gates
```

## Foundational Requirements

- Webhook receiver with Meta signature verification (`X-Hub-Signature-256` HMAC via
  `WHATSAPP_APP_SECRET_KEY`) and hub-challenge verify handshake — everything inbound depends on it.
- Facade with swappable transport: existing live provider + new deterministic stub (CI/e2e must run
  without Meta, mirroring the `OTP_MODE`/`KYC_PROVIDER=STUB` contracts).
- Cross-channel identity: OTP-verified phone as the join key (E1) gates status, delegates, and all
  case-data disclosure over WhatsApp.
- Token service: gates every WhatsApp→web action handoff.

## High-Risk Areas

| Area | Why |
|---|---|
| Webhook signature + replay handling | Only unauthenticated public inbound surface of the backend; edge-auth contract must exempt/accommodate Meta's calls |
| Token service (§26.5) | Pen-check launch gate: replay, expiry, scope containment; never a session |
| Conversation-hijack defense | Bot must never read case data to an unlinked/unverified number — enforced server-side, not in flow logic |
| Meta 24-hour service window | Agent replies outside the window require the `window_reopen` template; console adapter must detect and route |
| Delegate social engineering | §26.4.5 "my relative is handling it" rule — status-only, one per case, OTP-verified, no exceptions |
| LLM intent classification (D44) | Guardrail topics must route to human deterministically regardless of classifier output; classifier failure ⇒ human routing, never a guess |
| Consent enforcement | Router-enforced, never per-send-site (§26.4.6) — matches the existing §17 rule-table pattern |

## Cross-Cutting Concerns

- **Auth:** WhatsApp identities are phone-keyed, linked 1:1 to accounts via OTP (E1). Handoff
  tokens authorize one intent on one case — never sessions. Web landing endpoints validate
  same-origin redirect rules as everywhere else.
- **Data model:** WhatsApp link on user, conversation source labeling, bot conversation state,
  template registry, delegate grants, marketing/utility consent fields, jti redemption records.
- **Events:** all milestone/report/delegate sends are event-bus subscribers (§4.8) — no direct
  sends from services. State transitions already publish; new subscribers consume.
- **Determinism:** stub transport records outbound + injects inbound for e2e; `OTP_MODE`
  governs linking OTPs; intent classifier STUB is keyword-deterministic.
- **Observability:** §26.10 metrics instrumented from day one; Meta quality rating monitored (ops).

## System Implications

### Database
New tables (indicative — final at slice design): `whatsapp_links` (user↔number, 1:1),
`whatsapp_bot_sessions` (conversation flow state), `whatsapp_templates` (registry + approval
status), `case_delegates`, `handoff_token_redemptions` (jti single-use), consent fields/rows for
utility + marketing WhatsApp opt-ins (existing consent domain), conversation/message source
labeling columns. All via Alembic; raw strings in migrations per repo convention.

### API
- Public: `POST/GET /webhooks/whatsapp` (Meta), `GET /wa/{pay|upload|report}/{token}` frontend
  routes backed by token-redemption endpoints.
- Authenticated web: linking endpoints (send OTP / confirm), delegate CRUD (one per case,
  revoke), consent toggles, continuation short-code issuance.
- Admin: template registry, WhatsApp conversation surfacing in existing console, channel analytics.
- Bot reads case state **through the same service layer the dashboard uses** (§26.3.1) — no
  parallel query path.

### Security
- Signature-verified webhooks; raw-body HMAC before parsing.
- RS256 keypair management via Doppler; jti recorded server-side; `secrets` for all nonces/OTPs.
- Server-derived identity everywhere: sender phone → link lookup; bot capability matrix enforced
  in the service layer, not in flow copy.
- Edge-auth: webhook path must work through Cloudflare; direct-origin protection preserved for
  everything else.

## Ambiguities

Resolved at the initialize gate (see decision log D42–D47). Residual, carried as defaults:

- [ ] §26.3.2 state names vs existing `VerificationStatus` → D45: channel-level projection, no new
  case state machine. Revisit if intake-resumability needs its own persisted states beyond drafts.
- [ ] Console integration shape (new `ConversationType` vs source label on existing types) →
  decided at S2 design; PRD requires "one conversation object" across surfaces (§26.8).
- [ ] SMS-OTP fallback provider (§B pending) → D46: deferred, `TODO(gap):`; WhatsApp auth
  template is the only linking OTP transport at v1.
- [ ] Intent-LLM provider/model → D48 (amends D44): provider-agnostic facade; default provider +
  model chosen at S5 via settings, targeting Haiku-class-or-equivalent latency/cost.

## Recommended Implementation Order

1. S1 widget + attribution (independent, immediately live).
2. S2 channel foundation → S3 tokens → S4 linking (small, security-sensitive batches).
3. S5 bot core → S6 intake → S7 console adapter (medium batches).
4. S8 templates/consent/milestones → S9 delegates → S10 analytics (medium/large).
5. S11 live hardening + launch-gate checklist.

## Key Risks

- **Meta platform dependency** (accepted, §26.11): scam-saturated category; mitigation = strict
  opt-in, low template volume, quality-rating monitoring; containment = website remains canonical.
- **Approval lag on templates** (§26.7): draft + submit early — S8 registry ships before live
  template sends are possible; approval status tracked in-registry.
- **Live-wiring assets** (D43): WABA/green tick/number custody are business gates; live path can
  only be exercised end-to-end once Meta assets exist — stub keeps CI green regardless.
- **Solo-engineering delay risk** (J2): accepted in PRD; no timebox.

# Architecture Specification — WhatsApp Channel (cycle 2)

> Extends the as-built architecture in [MASTER-PRD.md](../MASTER-PRD.md) §4; cycle-1 spec archived
> at `docs.back/architecture-spec.md`. Governing PRD: [PRD.md](../PRD.md) §7. All placements below
> reuse existing patterns; final file paths confirmed at slice design, structure is binding.

## System Overview

One canonical backend, two thin surfaces (§7.3). WhatsApp traffic terminates at a signature-
verified webhook, is normalized by the facade, and flows into the **existing** communication
domain, event bus, and notification router. Outbound goes back through the facade to the existing
Cloud API provider (live) or a new deterministic stub (CI/e2e, D43). The bot engine is a
deterministic per-conversation state machine; only free-text intent classification is LLM-assisted
(D44), behind its own facade.

```
Meta Cloud API ──POST──▶ webhook receiver ──▶ facade.normalize ──▶ inbound dispatcher
                                                    │                    ├─▶ bot engine (sessions, flows, guardrails)
        stub transport (CI/e2e) ◀──┐                │                    └─▶ console adapter ─▶ communication domain
Meta Cloud API ◀── facade.send ◀───┴── bot replies / agent replies / notification router (templates)
```

## Bounded Contexts & Placement

| Component (§7.3.3) | Placement | Reuses |
|---|---|---|
| Webhook receiver | `app/domain/channel/whatsapp/webhook/` (controller + signature verifier) | raw-body HMAC pattern; Cloudflare/edge-auth exemption handled like other public webhooks |
| WhatsApp facade | `appodus_utils/integrations/messaging/providers/whatsapp/` — **existing** `whatsapp_business.py` (live send) + new `stub.py` (deterministic) + inbound normalization models | existing `MessageRouter`, WhatsApp payload models (templates, interactive) in `messaging/models.py` |
| Bot engine | `app/domain/channel/whatsapp/bot/` — session store, flow FSMs, guardrails, escalation | verification/service + submission-draft services via the same service layer the dashboard uses (§7.3.1, D45) |
| Intent classifier | `appodus_utils/integrations/intent/` facade (provider-agnostic, D48): `STUB` (keyword table) \| `ANTHROPIC` \| `OPENAI_COMPATIBLE` (base URL + model + key — covers OpenAI, DeepSeek, Groq, Ollama, …) | §4.13 facade pattern (`KYC_PROVIDER=STUB` shape); messaging provider-registry shape; provider API key via Doppler |
| Console adapter | extension of `app/domain/communication/` — WhatsApp-sourced messages join the existing conversation pipeline with source labeling; replies fan back through the facade | `ChatMessageState` machine, fraud scan (`fraud_scan.py`), SSE emitters |
| Fraud-scan pipeline | unchanged — WhatsApp text enters the same scan as web chat (WA-13) | `communication/service.py` |
| Token service | `app/domain/channel/whatsapp/handoff/` — RS256 issue/validate, jti single-use | `secrets` for nonces; idempotency-key storage pattern (§4.6) for redemptions |
| Template manager | `app/domain/channel/whatsapp/template/` — registry entity + admin endpoints | GenericRepo/Page pattern; DataTable on admin frontend |
| Notification router | extension of `app/domain/notification/` declarative rule table with a WhatsApp channel + consent gate | event-bus subscribers (§4.8); existing preference model |

**Frontend:** widget in the shared layout (`components/website/`), `/wa/{pay,upload,report}/[token]`
routes, delegate management on case detail, consent controls at payment confirmation + account
settings, admin template-registry and channel-analytics pages. All backend-proxied via the
existing rewrite; service files kept in sync with controllers per repo contract.

## Domain Model

| Entity | Purpose | Key fields (indicative) |
|---|---|---|
| `WhatsAppLink` | 1:1 OTP-verified phone↔account join (E1) | user_id (uq), phone (uq), verified_at, status |
| `WhatsAppBotSession` | per-conversation flow state | phone, current_flow, step, context JSON (text), last_inbound_at (30-day idle), unmatched_count |
| `WhatsAppTemplate` | §7.7 registry | name (enum-backed), category, version, meta_status, submitted_at |
| `CaseDelegate` | O2 slim delegate | verification_id (uq — one per case), name, phone, verified_at, revoked_at |
| `HandoffTokenRedemption` | jti single-use record | jti (uq), intent, case_id, redeemed_at |
| Consent additions | utility + marketing WhatsApp opt-ins | existing consent/preference models; timestamped, exportable (§7.8) |
| Message source labeling | one conversation object across surfaces (§7.8) | source/channel column on chat messages; `unofficial` flag for chat media |

All enums get real Python enums (repo rule); migrations keep raw strings.

## API Design (indicative)

- `GET/POST /webhooks/whatsapp` — hub-challenge verify + signed inbound. Public; signature is the
  auth. Never behind user auth; edge contract documented at S2.
- `POST /wa/handoff/redeem` — token validation for the three landing routes (frontend proxies).
- `POST /users/me/whatsapp-link/otp` · `POST /users/me/whatsapp-link/confirm` · `DELETE …` — E1.
- `POST /verifications/{id}/delegate` · `DELETE …/delegate` — O2.
- Admin: `GET/PUT /admin/whatsapp/templates` (Page[T]), `GET /admin/analytics/whatsapp`.
- Consent: existing consent/preference endpoints extended with the two new opt-ins.

## Auth Model

- **Webhook:** HMAC-SHA256 signature over raw body with `WHATSAPP_APP_SECRET_KEY`; verify token
  for the GET handshake. No session, no cookies.
- **Handoff tokens (§7.5):** RS256 JWT — claims `sub`, `case`, `intent ∈ {pay,upload,report}`,
  `exp = iat+15m`, `jti`. Redemption records jti; replays rejected. Token ≠ session: the landing
  flow authorizes exactly one action on one case; keypair via Doppler (`SECRET_ENV_KEYS`).
- **Bot identity:** sender phone → `WhatsAppLink` lookup server-side; unlinked numbers receive
  zero case data (WA-22) — enforced in the service layer, not flow copy.
- **Capability matrix (§7.3.4):** service-layer enforcement; bot cannot reach pay/report/account
  actions even if a flow bug asks.

## Determinism & Config

| Knob | Values | Contract |
|---|---|---|
| `WHATSAPP_PROVIDER` | `STUB` (default non-prod) \| `META` | stub records outbound + injects inbound via dev endpoints; e2e runs entirely on stub (D43) |
| `INTENT_PROVIDER` | `STUB` (default non-prod/test) \| `ANTHROPIC` \| `OPENAI_COMPATIBLE` | STUB = deterministic keyword table (D44/D48); `INTENT_MODEL` + provider base-URL/key knobs select the live target |
| `OTP_MODE` | existing contract | linking OTPs deterministic in test |
| RS256 keypair, intent-provider API key(s), existing `WHATSAPP_*` secrets | Doppler | committed env files placeholder-only; `test_env_hygiene.py` extended |

Dev endpoints (`/dev/whatsapp/inbound`, stub outbox reader) follow the existing `_require_non_prod()`
double gate.

## Eventing

No new bus. Milestones (`payment_confirmed`, `verification_started`, `inspection_complete`,
`report_ready`), delegate updates, and window-reopen sends are **subscribers** to existing domain
events; the notification router consults consent + preference before any send (WA-16, WA-27).
Report-ready email remains unconditional (Decision B).

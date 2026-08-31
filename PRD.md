# VERIPROPS MASTER PRD — §7: WhatsApp Channel (Verify)

**Version:** 1.0 (for incorporation into Master PRD v2.5)
**Status:** Specification complete — all decisions locked (Decision Record A–P)
**Scope:** Verify only. Marketplace/Monitor interactions are out of scope until those products exist.
**Precedence:** Subordinate to the Veriprops Constitution v1.0 and Master Blueprint per the document hierarchy. Conflicts resolve upward.

---

## 7.1 Positioning & Principles

WhatsApp is the **conversational front door**; veriprops.ng is the **vault**. All money movement, sensitive document handling, and report access occur exclusively on the verified domain. WhatsApp handles everything conversational: discovery, intake, status, and human contact.

**Standing principles (Trust Charter annex):**

1. **Payment pledge:** "Payments only ever happen at veriprops.ng — check the address bar before you pay." Stated in the bot welcome message, repeated in every payment handoff message, published on the website.
2. **Anti-impersonation protocol:** Official number **+234 916 762 4347** (wa.me/2349167624347) published on veriprops.ng, investor materials, and every certified report. Meta Business verification and green tick are hard launch gates. No other number ever contacts customers.
3. **Bot guardrail:** The bot never renders verification judgments, legal opinions, or property-specific assessments. It explains, routes, collects, and reports status. Judgments come only from humans and certified reports.
4. **Bot disclosure:** The bot identifies itself as automated in the welcome message.
5. **No outbound voice:** Veriprops never sends voice notes. Official communication is text from the verified number. Voice interaction happens only on scheduled calls.
6. **Evidence rule:** Only portal uploads and structured intake are canonical. Chat images and voice-note content are unofficial and never enter the verification file.

---

## 7.2 Decision Record (Locked)

| # | Decision | Locked choice |
|---|---|---|
| A | Payments | Website handoff only — never in-chat |
| B | Report delivery | WhatsApp notification + authenticated portal link |
| C | Transport | Meta Cloud API direct (no BSP); SMS-OTP fallback provider pending (§B) |
| D | Bot build | Custom, day one, behind facade layer |
| E | Identity linking | OTP-verified phone as cross-channel join key, both directions |
| F | Status updates | Opt-in utility milestone templates (~3–4 per verification) |
| G | Human coverage | 8am–8pm WAT weekdays + Saturday morning; stated response times outside |
| H | Launch scope | Full scope, frozen; amended once to add slim delegate v1 (O2) |
| I | Sequencing | Launch gated on MVP + bot both production-ready |
| J | Downside cap | None — accepted risk in §B; reopens on raise-close or investor launch-date request |
| K | Handoff interface | WhatsApp routed into existing admin chat console (SSE, fraud-scanned) |
| L | Language | English only at v1 |
| M | In-chat documents | Portal uploads canonical; chat images unofficial, customer redirected |
| O | Third-party access | Web-authorized delegate: OTP-verified, status-only, one per case, revocable |
| P | Marketing consent | Separate unticked marketing opt-in captured at payment confirmation |

---

## 7.3 Architecture: One System, Two Surfaces

There is **one canonical backend**. WhatsApp and the website are thin clients reading and writing the same state through the same API. Neither channel owns data; both render it.

### 7.3.1 Canonical objects

| Object | Canonical home | WhatsApp rendering | Website rendering |
|---|---|---|---|
| Customer identity | Backend, keyed on OTP-verified phone | The chat itself | Account / login |
| Verification case | Backend state machine | Status messages, milestone templates | Dashboard, full detail |
| Conversation | Admin console pipeline | Native chat | Web chat widget, same thread |

### 7.3.2 Verification case state machine

```
enquiry → intake_in_progress → intake_complete → payment_pending
→ paid → verifying → field_inspection → report_ready → delivered → closed
```

- Both surfaces read the same state; either can advance it where the capability matrix permits.
- All state transitions emit events; the notification router and milestone templates subscribe to events, never poll.
- The bot reads case state **through the same API endpoints the website dashboard uses**. No parallel query path. (Prevents the two surfaces ever showing different statuses for the same case.)

### 7.3.3 Components

| Component | Responsibility |
|---|---|
| **Webhook receiver** | Terminates Meta Cloud API webhooks; verifies signatures; normalizes inbound messages into the internal message schema |
| **WhatsApp facade layer** | Abstraction over Meta Cloud API (Dojah pattern). All send/receive goes through it; transport is swappable without system-wide change |
| **Bot engine** | Structured conversation flows (state-per-conversation), intent matching, guardrail enforcement, escalation logic |
| **Console adapter** | Feeds normalized WhatsApp messages into the existing SSE admin chat pipeline with source labeling; carries agent replies back out through the facade |
| **Fraud-scan pipeline** | Existing SSE scanning applies to all WhatsApp text; (v1.1) voice-note transcripts enter the same pipeline |
| **Token service** | Issues and validates signed single-use handoff tokens (§7.5) |
| **Template manager** | Registry of Meta-approved templates, versions, and approval status |
| **Notification router** | Per-customer channel preference; dispatches milestone templates (opt-in) and email |

### 7.3.4 Capability matrix

| Action | Website | WhatsApp |
|---|---|---|
| Learn / FAQ / pricing | Full | Full (bot) |
| Start & complete intake | Full | Full (bot flow) |
| Upload documents | Full — **canonical** | Handoff (chat images unofficial) |
| Pay | Full — **only** | Handoff (signed link + domain-check message) |
| Check status | Full | Full (query or opt-in milestones) |
| View report | Full — **only** | Handoff (notification + portal link) |
| Talk to human | Full (web chat) | Full |
| Account / settings / delegate management | Full | Not offered |

---

## 7.4 Website-Side Implementation

### 7.4.1 Chat widget

- **Placement:** Floating action button, bottom-right, all public and authenticated pages **except inside the payment flow** (reduces drop-off at the highest-value moment).
- **Visual:** Official WhatsApp logo per Meta brand guidelines, WhatsApp green (#25D366), subtle entrance after page load. No custom chat UI at v1 — the button deep-links out.
- **Link:** `https://wa.me/2349167624347?text=<prefill>` where prefill = "Hi Veriprops! [ref: <page-code>]". Page code enables channel attribution (e.g., `web-home`, `web-pricing`, `web-report-sample`).
- **Behavior:** Opens WhatsApp app on mobile, WhatsApp Web/desktop on desktop, in a new tab/context. `aria-label="Chat with Veriprops on WhatsApp"`. Loaded async; zero cumulative layout shift.
- **Concierge phase:** Same widget, same number, live now against the free WhatsApp Business app. No code change required at API cutover — only the backend behind the number changes.

### 7.4.2 Handoff landing endpoints (WhatsApp → website)

Three token-gated endpoints consume signed single-use action tokens (spec §7.5):

| Endpoint | Intent | Lands the customer at |
|---|---|---|
| `/wa/pay/<token>` | `pay` | Payment page for that case, pre-authenticated for that action |
| `/wa/upload/<token>` | `upload` | Document upload for that case |
| `/wa/report/<token>` | `report` | Report view for that case (post-delivery) |

Requirements:
- Landing page **acknowledges origin**: "Picking up where you left off: payment for VP-1042." Silent context loss is a spec violation.
- Expired/used token → friendly expiry page with one-tap "Get a new link in WhatsApp" (deep link back to the chat; bot resends **on request only**, never auto-resends).
- Tokens grant access to the named action on the named case only — never a full session.

### 7.4.3 Website → WhatsApp continuation

- "Continue on WhatsApp" affordances on the dashboard and mid-intake use `wa.me/2349167624347?text=Continue verification <case-short-code>`.
- Case short codes are **opaque** (e.g., VP-1042) — never address or customer name (WhatsApp preview text leaks).
- Bot resolves the short code against the OTP-linked identity. If the sending number is unlinked, the bot runs the linking flow (§7.4.4) first, then resumes with context acknowledgment.
- Bot never reads case data to an unverified number under any circumstances (conversation-hijack defense).

### 7.4.4 OTP account-linking flow (E1)

- **Web → WhatsApp:** User enters phone number in account settings → backend sends OTP via WhatsApp authentication template (primary) or SMS (fallback, provider pending §B) → user enters code on the website → link established.
- **WhatsApp → web:** Unlinked number requests something requiring identity → bot sends a signed link to a web page where the user logs in / registers, then confirms an OTP delivered to that WhatsApp number → link established → bot resumes.
- Link state is one-to-one: one WhatsApp number per account. Number change: re-verification flow on the web side; the old WhatsApp thread goes cold (no case data) until re-linked.

### 7.4.5 Delegate management (O2, slim v1)

- Buyer (account holder) authorizes **one delegate per case** from the case detail page: enters delegate name + phone number.
- Delegate's number is OTP-verified via the same E1 mechanics (narrower grant) before any visibility begins.
- Delegate receives **status milestones only** — never documents, reports, chat history, or intake data.
- Revocable instantly from the same page; revocation takes effect on the next event.
- Bot behavior toward delegates: identifies them by role ("You're receiving updates on VP-1042 as a delegate"), answers status queries for that case only, routes everything else as a new enquiry.
- Non-delegate third parties asking about any case: warmly treated as a new enquiry; told the account holder can share updates or authorize them as a delegate. No exceptions — "my relative is handling it" is the social-engineering script this rule exists to defeat.

### 7.4.6 Consent capture (F1 + P1)

At payment confirmation, two **separate, unticked** controls:

1. **Utility opt-in:** "Send me progress updates about this verification on WhatsApp." → gates milestone templates.
2. **Marketing opt-in:** "Send me occasional Veriprops news and offers on WhatsApp." → stored as a distinct consent field with timestamp; gates all future marketing templates (incl. Marketplace launch audience at month 14).

Both revocable from account settings and via STOP-style keywords in chat. Consent state lives on the customer object; the notification router enforces it — enforcement is never left to individual send-sites.

---

## 7.5 Handoff Token Specification

- **Format:** Signed JWT (RS256).
- **Claims:** `sub` (customer id) · `case` (case id) · `intent` (`pay` | `upload` | `report`) · `exp` (issue + 15 min) · `jti` (single-use nonce).
- **Single-use enforcement:** `jti` recorded server-side on redemption; replays rejected.
- **Scope:** Token authorizes only the named intent on the named case. It is not a session. Completing the action does not log the user into the account.
- **Threat rationale:** A forwarded or leaked WhatsApp message exposes at most one expired, single-use, single-action link — never an account.

---

## 7.6 Bot Functional Specification (v1 launch scope — frozen)

### 7.6.1 Welcome flow
On first contact (or after 30 days idle): greeting + **bot disclosure** ("I'm Veriprops' automated assistant — I can bring in a human anytime") + **payment pledge** + top-level menu: *Learn how Verify works · Start a verification · Check my status · Talk to a human · Pricing*.

### 7.6.2 Flows

| Flow | Behavior |
|---|---|
| **FAQ / Learn / Pricing** | Structured answers from a maintained content set. Answers only what the content set covers; everything else → human routing. |
| **Intake** | Step-by-step structured flow collecting the same fields as web intake (property location, type, documents held, seller relationship, timeline). Writes to the canonical case via the shared API. On completion → payment handoff. Partial intake is resumable on either surface. |
| **Payment handoff** | Issues `pay` token link + pledge repetition + domain-check instruction. Never a payment inside chat, never a raw Paystack link. |
| **Status** | Linked numbers: resolves case(s); if multiple, asks which (by short code). Unlinked numbers: offers linking, never reads data. |
| **Milestones (opt-in)** | Templates on state-machine events: payment confirmed · verification started · field inspection complete · report ready (+ portal link). |
| **Report delivery** | `report_ready` → notification template + `report` token link. Email always receives report-ready regardless of WhatsApp preference (durable record). |
| **Human escalation** | Explicit request, two consecutive unmatched intents, or any guardrail-triggering topic → routed to console with full context. Within G1 hours: "a team member is joining." Outside: stated response time. |
| **Refund / cancellation** | Always human. Bot acknowledges, routes, states response window. Resolution under website refund policy; confirmation via portal + email. Money decisions are never bot territory. |

### 7.6.3 Non-text inbound handling

| Input | Behavior |
|---|---|
| **Images / documents** | Acknowledge warmly → state the evidence rule → issue `upload` token link → image flagged unofficial in console, never enters the verification file. |
| **Voice notes** | v1: acknowledge ("A team member will listen and reply within [window]") → route to console flagged as audio. Never silently dropped. v1.1: transcription-assist (§7.9). |
| **Location pins, contacts, other media** | Acknowledge → route to human. |

### 7.6.4 Guardrails (hard constraints in the bot engine)

- No verification judgments, legal opinions, Trust Score interpretations, or property-specific assessments — these intents route to human, always, with no partial answers.
- No pricing negotiation, no refund decisions, no promises of outcomes or timelines beyond published SLAs.
- Out-of-scope or low-confidence intent → human routing, never a guess. English only; non-English inbound → polite English response + human routing.

### 7.6.5 Failure behavior

Health-checked pipeline. On bot/API failure: auto-reply fallback ("We're having a technical issue — a human will respond within [G1 window]") + console alert. An outage must never look like a scam that stopped replying.

---

## 7.7 Meta Templates Registry (draft & submit early — approval lag is on the critical path)

| Template | Category | Trigger |
|---|---|---|
| `otp_auth` | Authentication | E1 linking flows |
| `payment_confirmed` | Utility | State event, opt-in |
| `verification_started` | Utility | State event, opt-in |
| `inspection_complete` | Utility | State event, opt-in |
| `report_ready` | Utility | State event (opt-in for WhatsApp; email always) |
| `window_reopen` | Utility | Agent reply needed outside Meta's 24-hour service window |
| `delegate_status` | Utility | Delegate milestone delivery |

Marketing templates: none at v1. Drafted only when a consented campaign is planned (P1 audience).

---

## 7.8 Compliance, Data & Legal

- **NDPA:** Privacy policy discloses the WhatsApp channel, cross-border transit via Meta infrastructure, consent basis for utility and marketing messages, and (at v1.1) third-party STT processing of voice notes. Consent records timestamped and exportable.
- **Terms of service:** Explicitly cover WhatsApp as a communication surface under the §3.5 liability framework (1× fees-paid cap). Chat logs are retained business records; retention **duration** is a §B counsel sign-off item.
- **Chat logs:** Retained, exportable, and covered by the same access controls as case data. Conversation log is complete across both surfaces (one conversation object).
- **Evidence chain:** Only portal uploads and structured intake are canonical (M1). Voice-note and chat-image content never enters the verification file.

---

## 7.9 v1.1 Backlog (explicitly NOT launch-gating)

1. **Voice-note transcription-assist:** Server-side STT behind the facade layer. Transcripts flow into the SSE fraud-scan pipeline and display alongside the audio player in the console. Assist-quality only; audio remains source of truth; agents confirm anything consequential by listening. Bot may answer only clear simple-intent transcripts with a soft confirm; all else routes to human.
2. **Delegate enhancements:** multiple delegates, granular permissions — only if demanded by data.
3. **Status-sync depth / richer flows** harvested from the concierge-phase conversation corpus.
4. **Language:** Pidgin evaluated against real conversation data (L3 review).
5. **In-chat payment re-examination:** only after anti-impersonation protocol is battle-tested, and only with a fresh decision.

Scope discipline: anything not in §7.6 is v1.1 by definition, regardless of merit ("and more" clause, frozen).

---

## 7.10 Analytics

Instrumented from day one:

| Metric | Why it matters |
|---|---|
| **Intake-completed → payment-completed (seam conversion)** | The cost of the A1 trust boundary, measured. The single most important number in this channel. |
| WhatsApp-attributed enquiries (by widget page code) | Channel demand validation |
| Enquiry → intake-started rate | Bot flow effectiveness |
| Human-escalation rate & reasons | Bot coverage gaps; feeds flow iteration |
| Template opt-in rates (utility, marketing) | Consent asset growth; Marketplace launch audience |
| Meta quality rating | Platform-dependency early warning |
| Voice-note volume | v1.1 transcription-assist trigger data |

---

## 7.11 Launch Gates & Operational Checklist

**Hard gates (launch cannot occur without):**
- [ ] Meta Business verification approved; green tick granted
- [ ] All §7.7 templates approved
- [ ] Number custody confirmed: +2349167624347 registered to Veriprops Technologies Ltd, SIM/eSIM under founder control, documented
- [ ] Fraud-scan pipeline verified against WhatsApp-sourced messages
- [ ] Token service pen-checked (replay, expiry, scope containment)
- [ ] Failure fallback tested (kill the bot, observe the auto-reply + alert)
- [ ] ToS + privacy policy updated per §7.8

**Operational readiness:**
- [ ] Console rota covering G1 hours (VNM + founder at launch; logged as real VNM capacity cost)
- [ ] Concierge → Cloud API cutover scheduled as a deliberate step (number binding is one-way: post-binding, the number no longer works in the consumer/Business app)
- [ ] Conversation-theme tracker live from first concierge chat (feeds bot flows + content/SEO)

**Accepted risks (§B cross-reference):**
- J2: no timebox on the launch gate; solo engineering; delay risk unbounded by design; gate enlarged once by O2 (by choice, dated). Reopens on raise-close or investor launch-date request.
- Meta platform dependency: property is a scam-saturated category under aggressive automated enforcement. Mitigations: strict opt-in discipline, low template volume, no purchased lists, quality-rating monitoring. Containment: veriprops.ng remains the canonical channel — a ban is a bruise, not an amputation.

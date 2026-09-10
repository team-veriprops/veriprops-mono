# WhatsApp channel — launch runbook (PRD §26.11)

Everything in §26.11 that a person has to do, in the order it has to be done. The code-side
items are already green and are listed here only so the checklist is complete in one place;
the ⊘ items depend on assets Meta or a human has to provide.

**This runbook is executed once, deliberately, at cutover.** Two of its steps are one-way.

---

## Before you start

- The number: **+2349167624347**.
- **Staging has already run this path** (D88): it is `WHATSAPP_PROVIDER=meta` against Meta's
  developer test number, on the same DeepSeek classifier as prod. So §3's live smoke is a
  re-run on the real number, not first contact — anything below that has never worked on
  staging is a defect to fix before cutover, not during it. Dev and test stay stubbed;
  `ENVIRONMENT=test` **requires** the stub and `prod` requires `meta`, enforced at boot, so
  CI can never reach Meta and production can never launch onto the stub.
- The Doppler keys the live path needs, in the `prd` config of `veriprops-backend`:
  `WHATSAPP_BUSINESS_ACCESS_TOKEN`, `WHATSAPP_BUSINESS_ACCOUNT_ID`,
  `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_APP_SECRET_KEY`,
  `WHATSAPP_BUSINESS_WEBHOOK_VERIFY_TOKEN`, the §26.5 RS256 keypair
  (`WHATSAPP_HANDOFF_PRIVATE_KEY` / `WHATSAPP_HANDOFF_PUBLIC_KEY`), and
  **`INTENT_API_KEY`** — a **DeepSeek** key (D87). A missing key is the one omission that
  does not fail loudly: the classifier degrades to `UNKNOWN`, so every free-text turn routes
  to a human and the bot looks alive but useless. It logs a warning once and nothing else.
- **The two identifiers carry no code default** (D88). `WHATSAPP_PHONE_NUMBER_ID` and
  `WHATSAPP_BUSINESS_ACCOUNT_ID` used to default to production's, which stopped being safe
  the moment staging ran `meta` — a forgotten `stg` value would have sent QA traffic from the
  official number. The app now refuses to boot on `meta` without both. Set them per config,
  and check `stg` names the **test** number before any staging deploy.
- `stg` needs the same set as `prd`, with the test number's own ids and its own handoff
  keypair — `handoff_keys()` refuses to mint an ephemeral pair outside dev/test, so without
  one every `/wa/*` link fails there.

---

## 1. Hard gates

### 1.1 Meta Business verification ⊘
Business verification approved and the green tick granted on the number. Nothing in the app
checks this; it is the anti-impersonation anchor §26.1.2 rests on, and a customer's only
independent way to tell our number from a copy.

### 1.2 Template approval ⊘ (code-side: green)
All seven §26.7 templates are declared, bodied, and **sent by real code paths** — `otp_auth`,
`window_reopen`, the four milestones, and `delegate_status`. Submission and approval are
external.

- Submit each from the Meta Business Manager.
- Then `/admin/config/whatsapp-templates` → **Sync**, and confirm every row reads `APPROVED`.
  `NOT_FOUND` is ours, not Meta's: declared but never submitted, and it is the state this
  gate is actually asking about.
- **Check the `otp_auth` button shape matches what we send.** An authentication template's
  approved button is part of its contract, and a mismatch fails at send time, on the one
  message a customer is waiting for.

Approval status never blocks a send by design — a stale sync must not take the channel down.
So this gate is a human reading the registry, not a check the code performs.

### 1.3 Number custody ⊘
+2349167624347 registered to Veriprops Technologies Ltd, SIM/eSIM under founder control, and
**documented** — where the SIM physically is, who can request a port, and what recovery looks
like. The number is the anti-impersonation anchor; losing control of it is the worst
single-point failure in the channel.

### 1.4 Fraud scan over WhatsApp-sourced messages ✅
Verified by `stage_whatsapp` in the drive-through: an inbound WhatsApp message goes through
the same send-time scan as web chat and lands in the same console (Decision K). Re-confirm on
the live path at step 3.

### 1.5 Token pen-check — automated ✅ / human ⊘
Automated coverage for replay, expiry, wrong-intent, wrong-case and tampered signatures is in
the unit suite and the drive-through. The remaining items are in
[handoff-token-pen-check.md](handoff-token-pen-check.md) and need a person with a proxy:
- Replay a redeemed token from a different IP and browser.
- Strip and re-sign with `alg: none` and with HS256 keyed on the public key.
- Confirm every rejection is **not-found**, never forbidden, and that the copy is identical
  for expired, spent and forged.

### 1.6 Failure fallback drill ✅ (re-run live at step 3)
`POST /dev/whatsapp/fail-next-turn` arms one real bot turn to fail; the drive-through then
asserts the customer gets the §26.6.5 apology plus a human promise, an admin gets
`BOT_PIPELINE_FAILED`, the fault is one-shot, and §26.10 counts it under `PIPELINE_FAILURE`.
The endpoint is production-gated twice and refuses to arm in production, so the live re-run
is the *observational* version: watch a real classifier outage, or simulate one by revoking
the intent provider's key in staging.

### 1.7 ToS and privacy policy ✅ (counsel sign-off ⊘)
The §26.8 clauses are live in three documents at version `1.1.0`: Platform Terms (WhatsApp as
a communication surface under the §3.5 cap, plus the two absolute limits), Privacy Policy
(the channel, the cross-border transit via Meta, the two consent bases, delegate scope), and
Communication Recording (one conversation record across both surfaces).

Two things to know before deploying:
- **Every existing account is asked to re-accept.** A new cross-border transfer disclosure is
  a material change; that is the correct NDPA answer and it is a visible event on the day.
- All three stay `DRAFT` until counsel signs off, and **retention duration** is still their
  call (§B). The clauses name the policy rather than a number so the duration can land
  without another version bump.

---

## 2. Operational readiness

- **Console rota covering G1 hours** ⊘ — VNM plus founder at launch, logged as a real VNM
  capacity cost. Hours are `system_config` (`support_hours_start`/`_end`/
  `support_saturday_end`), so the bot's promise and the rota must be set to the same numbers.
  The bot quotes these to customers; a rota that does not match them makes the bot lie.
- **Conversation-theme tracker** ⊘ — live from the first concierge chat. §26.10's escalation
  reasons are the automated half of this; the manual half is reading what people actually ask.

---

## 3. Cutover — the one-way step

The number binding is **irreversible**: once bound to the Cloud API, +2349167624347 stops
working in the consumer and Business apps. Schedule it, do not drift into it.

1. Freeze concierge replies and tell the rota the channel is going dark for the window.
2. Bind the number to the Cloud API in Meta Business Manager.
3. Point the webhook at `https://<prod>/api/channel/whatsapp/webhook` and complete the hub
   handshake with `WHATSAPP_BUSINESS_WEBHOOK_VERIFY_TOKEN`.
4. Deploy with `WHATSAPP_PROVIDER=meta`.

### Live smoke (manual, never CI)
From a real handset, in this order — each step depends on the last:

| # | Do | Expect |
|---|---|---|
| 1 | Message the number from the website widget | §26.6.1 welcome: bot disclosure, payment pledge, five-item menu |
| 2 | Check `/admin/messages` → WhatsApp | The thread is there, `ChannelBadge` says WhatsApp, and §26.10 counted an enquiry with the widget's page code |
| 3 | Reply from the console | It arrives on the handset; the thread goes sticky-`HUMAN` and the banner says so |
| 4 | Hand back, then ask "what does it cost?" | Bot answers with live pricing (never a literal) |
| 5 | Ask "is this property genuine?" | Refused and routed to a person — the §26.6.4 guardrail, on the live classifier |
| 6 | Link the number from `/account/whatsapp` | `otp_auth` template arrives; the button matches 1.2 |
| 7 | Say "how do I pay?" on a quoted case | A `/wa/pay/<token>` link that opens and completes |
| 8 | Drive a case to a milestone | The §26.6.2 template arrives — and only if utility consent is on |
| 9 | Reply STOP | Answered in one turn by the bot; both consents off in `/account/whatsapp` |
| 10 | Send a voice note | The §26.6.3 acknowledgement, flagged as audio in the console |
| 11 | `/admin/analytics` → Channel tab | Every count above has moved; sync the quality rating and confirm Meta's real value |

Anything that fails here is a launch blocker, not a follow-up.

---

## 4. After launch

- Watch the Meta quality rating for the first fortnight. `YELLOW` is the signal to slow
  template volume, not to wait for `RED`.
- Watch §26.10's seam conversion. It is the cost of the A1 trust boundary and the number the
  channel is judged on.
- Containment, if the worst happens: veriprops.ng stays the canonical channel. A ban is a
  bruise, not an amputation.

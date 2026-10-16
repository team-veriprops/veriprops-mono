# This Captures things to note about this project

1. Agents must specify their availability to receive tasks.
2. Run app wide audit to verify guidelines were followed.
3. Fix Oauth session cookie issue

# Test Users

Seeded QA logins come from `POST /api/dev/seed` (its response payload lists them); never record passwords here.

# Pending owner actions (checked 2026-10-15)

**Background you need.**

- Veriprops deploys from GitHub Actions only (`.github/workflows/deploy.yml`):
  - push to `dev` → dev
  - push to `staging` → staging
  - push to `master` → production
- Each deploy runs the tests, then the database migrations, then the backend, the frontend and the Cloudflare "sweep" Worker.
- Secrets are not in git. They live in **Doppler**: project `veriprops-verf-backend` (and `veriprops-verf-frontend`), one config per environment: `dev`, `preview` (= staging, `APPODUS_ACTIVE_ENV=staging`) and `prd`.
- The pipeline reads Doppler through the GitHub **Environment** secrets `DOPPLER_TOKEN_BACKEND` / `DOPPLER_TOKEN_FRONTEND`, and passes every key to `vercel deploy` itself. There is **no Doppler→Vercel sync** and there are no Vercel dashboard env vars.
- Production checks its own settings at start-up (`backend/main/app/config/settings.py`, `_enforce_live_integrations_in_production`) and **refuses to start** if a required key is missing, naming every missing key in one error. The migration step runs the same check, so a missing key fails the deploy before anything ships.
- **A key that exists in Doppler with an empty value counts as missing**, and it also hides the committed file's placeholder. Never store a blank value in Doppler; delete the key instead.

To generate any random secret below:
`python -c "import secrets; print(secrets.token_urlsafe(48))"`

**Production right now:** every key the start-up check requires is set, so a deploy would start. What still blocks real customers: Dojah's sandbox key (A1), this branch's R2 code not yet deployed (A2), test payment keys (A3), WhatsApp IDs and handoff keys (A4), and the legal sign-offs (A5).

## A. Go-live blockers

**A1. Dojah (identity checks for agents).**

- **What:** agent onboarding checks identity on Dojah: a liveness check on the selfie, then the BVN or NIN matched to that photo. Staging uses Dojah's **sandbox** (`DOJAH_BASE_URL=https://sandbox.dojah.io` in `backend/.env.staging`); production uses the **live** host (`backend/.env.prod`). Dev uses a stub and needs nothing. Staging's sandbox keys are in place. **`prd` also holds a sandbox key** (`test_sk_…`).
- **Why:** production starts with a sandbox key, then every live identity check is rejected by Dojah's live host, so no agent can be verified.
- **How:**
  1. Complete Dojah's go-live (business verification), then replace `prd`'s `DOJAH_APP_ID` and `DOJAH_PRIVATE_KEY` with the **live** App ID and Secret Key (`prod_sk_…`). Sandbox keys don't work against the live host. `dev` doesn't need Dojah keys at all (it uses the stub).
  2. On the app, enable **Liveness**, **BVN lookup with selfie** and **NIN lookup with selfie**.
  3. Fund the Dojah wallet. Each agent check is two paid calls (liveness, then BVN or NIN).
  4. Leave any IP allowlist off: Vercel has no fixed outgoing IPs.
  5. **Developers → Webhooks: leave it empty, subscribe nothing.** Dojah's webhooks report on its KYC widget, SMS, address and AML-monitoring services, none of which Veriprops uses. Our liveness and BVN/NIN checks are direct API calls whose result comes back in the same call, so no event would ever arrive, and the backend has no Dojah receiver (`/api/webhooks/dojah` doesn't exist).
     If the dashboard won't save without a URL, tell Claude: a receiver is a small change (verify `x-dojah-signature` against the raw body with `DOJAH_PRIVATE_KEY`, acknowledge, log).
- **Done when:** from `backend/`, `doppler run --project veriprops-verf-backend --config preview -- python scripts/live_smoke.py --only dojah --selfie <a photo of your face>` prints PASS (it uses Dojah's sandbox BVN `22222222222`).

**A2. Deploy the R2 storage code.**

- **What:** the R2 buckets, tokens and Doppler values are in place for staging and production, and staging's bucket passed the live smoke probe (put, read, delete) using this branch's code. The code that lets the app reach R2 (`STORAGE_*` settings) is **not committed or deployed yet**, so deployed staging and production still run the old AWS-only storage code.
- **How:** merge and deploy the branch that carries it (dev → staging → master).
- **Done when:** an agent's evidence photo uploads and opens on staging, then on production. (`live_smoke.py --only s3` refuses production, so production is checked through the app.)

**A3. Live payment keys.**

- **What:** Doppler `prd` holds **test-mode** keys for both gateways (`PAYSTACK_SECRET_KEY` is `sk_test_…`, the Flutterwave key is a `…TEST…` key). Staging should keep its test keys: `live_smoke.py` refuses live ones.
- **How:** at go-live, replace `PAYSTACK_SECRET_KEY`, `PAYSTACK_PUBLIC_KEY`, `FLUTTERWAVE_SECRET_KEY`, `FLUTTERWAVE_PUBLIC_KEY` and `FLUTTERWAVE_WEBHOOK_SECRET` in `prd` with **live** values, and register the production webhooks in each dashboard's **live** mode (staging's in test mode; see E1).
- **Done when:** a real ₦100 payment on production turns a case PAID.

**A4. WhatsApp IDs and handoff keys.**

- **What:**
  - The permanent access tokens are in place for `preview` and `prd` (verified: valid, never expire, both WhatsApp permissions). But the **IDs don't match what the tokens can reach**:
    - Staging: the test number (`WHATSAPP_PHONE_NUMBER_ID` `1325374370663269`, `+1 555-204-0880`) works, but `WHATSAPP_BUSINESS_ACCOUNT_ID` `1425830056168082` can't be read, so template sync fails.
    - Production: neither the phone id `766140453239478` nor the account id `1412930669928110` (`backend/.env.prod`) can be read, so production can't send.
  - `WHATSAPP_HANDOFF_PRIVATE_KEY` / `WHATSAPP_HANDOFF_PUBLIC_KEY` are **missing** everywhere. They sign the one-time `/wa/pay`, `/wa/upload` and `/wa/report` links the bot sends; staging and production refuse to sign without them, so every such link fails.
- **How:**
  1. Staging: developers.facebook.com → the staging app → WhatsApp → **API Setup** → copy the **WhatsApp Business Account ID** shown under the test number → Doppler `preview` `WHATSAPP_BUSINESS_ACCOUNT_ID`.
  2. Production: Business Settings → Users → System users → `Whatsapp-Messenger-Prod` → **Assign assets → WhatsApp accounts** → the production WhatsApp Business Account → **Full control** (no new token needed). If it's already assigned, check in WhatsApp Manager that the account and phone number ids match `backend/.env.prod` (tell Claude the right ones), and that +2349167624347 has been moved onto the Cloud API (the irreversible step in G).
  3. Generate a keypair per environment (Git Bash):

     ```
     openssl genrsa -out handoff.pem 2048
     openssl rsa -in handoff.pem -pubout -out handoff.pub
     ```

     Paste the files' contents as `WHATSAPP_HANDOFF_PRIVATE_KEY` and `WHATSAPP_HANDOFF_PUBLIC_KEY`. Use **different** pairs for `preview` and `prd` (optionally `dev`). Delete the files afterwards.
- **Done when:** Claude's read-only Meta check reads the number and its templates for both environments, and the bot's "pay" reply on staging opens the pay page for the right case.

**A5. Legal sign-off on all nine draft documents.**

- **What:** 9 of the 10 legal documents ship marked **DRAFT** (`backend/main/app/domain/user/auth/consent/content/__init__.py`). Only the Report Disclaimer is final.
  - Waiting on the WhatsApp chat-retention decision: Platform Terms, Privacy Policy, Communication Recording.
  - Also draft: Agent Terms, Verification Terms, Verification Disclaimer, Findings & Opinion Acknowledgement, Jurisdiction & Platform-Only, Refund & Cancellation Policy.
- **Why:** customers accept these before paying; drafts must not govern real money. See also H.
- **Done when:** counsel has signed off each one and it is marked final in that file.

## B. Security clean-up

**B1. Rotate the two Google service-account keys.**

- **What:** the Firebase key (push) and the "contracts" Google key (Drive/Docs) were once committed to git under `backend/service_accounts/`. The files are now untracked, but they remain in git history, which we chose not to rewrite.
- **Why:** anyone with a copy of the repo history holds working credentials to the Google project. (Push notifications aren't built yet, so this is a security clean-up, not a feature blocker.)
- **How:**
  1. console.cloud.google.com → IAM & Admin → Service accounts → open the Firebase Admin SDK account → Keys → Add key → JSON (downloads a file).
  2. On the same page, delete the old key.
  3. Do the same for the contracts account.
  4. Encode each file on one line: Git Bash `base64 -w0 key.json`.
  5. Put the Firebase output in Doppler as `FIREBASE_CREDENTIALS_JSON_B64` and the other as `GOOGLE_SERVICE_ACCOUNT_JSON_B64`, in `dev`, `preview` and `prd`.
  6. Delete the downloaded files.
- **Done when:** the Keys tab of both accounts shows only the new key.

## C. Messaging, email and sign-in providers

**C1. Twilio (SMS to non-Nigerian numbers, and the backup SMS route).**

- **What:** the three keys are now set, **but the values are wrong**: `TWILIO_ACCOUNT_SID` and `TWILIO_AUTH_TOKEN` hold the same 64-character string, and `TWILIO_PHONE_NUMBER` has no leading `+`. Twilio's Account SID is `AC` + 32 hex characters, the Auth Token is 32 hex characters, and the number must be E.164 (`+1…`).
- **How:** Twilio console → Account Info → copy the **Account SID** and **Auth Token**; buy or pick a sending number. Put `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` and `TWILIO_PHONE_NUMBER` in `preview` and `prd`. Messages go out with the sender name `veriprops`, so enable **Alphanumeric Sender ID** in Twilio's messaging settings. Fund the account.
- **Done when:** `live_smoke.py --only sms_twilio --intl-phone <non-Nigerian handset>` prints PASS on `preview`.

**C2. Termii (SMS to Nigerian numbers).**

- **How:** register the sender ID **`veriprops`** in Termii. The app sends on Termii's `generic` route, which can't reach numbers on Nigeria's do-not-disturb list, so ask Termii to enable DND delivery for that sender. Fund the account; staging sends real OTPs too.
- **Done when:** F3 below passes.

**C3. Email sending domain.**

- **What:** staging and production send as `noreply@veriprops.ng` through Resend, then Mailjet, then AWS SES.
- **How:**
  1. Verify `veriprops.ng` in **Resend**, **Mailjet** and **SES** (in the `AWS_REGION_NAME` region, and request SES production access, or it only sends to verified addresses).
  2. In Cloudflare DNS add each provider's DKIM records, **one** SPF record that includes all three, and a DMARC record.
  3. Limit the AWS IAM user behind `AWS_ACCESS_KEY` to `ses:SendEmail`; it no longer needs S3.
  4. Make sure `noreply@`, `support@` and `admin@veriprops.ng` are real inboxes (the super admin's password resets go to `admin@`).
- **Done when:** `live_smoke.py --only email_resend,email_mailjet,email_ses --email <your inbox>` passes and the mails land outside spam.

**C4. Google sign-in.**

- **How:** Google Cloud console → APIs & Services → Credentials → the OAuth client all environments use → Authorized redirect URIs:
  - `https://veriprops.ng/api/users/auth/oauth/google/callback`
  - `https://staging.veriprops.ng/api/users/auth/oauth/google/callback`
  - `https://dev.veriprops.ng/api/users/auth/oauth/google/callback`
  - `http://localhost:3000/api/users/auth/oauth/google/callback`

  Then OAuth consent screen → **Publish app**; in testing mode only listed test users can sign in.
- **Apple and Facebook sign-in are deferred** (decision 2026-10-11). Their buttons stay hidden (`NEXT_PUBLIC_OAUTH_APPLE_DISABLED` / `NEXT_PUBLIC_OAUTH_FACEBOOK_DISABLED=true`), so nothing is needed for them now.

**C5. WhatsApp on staging.**

- **What:** staging talks to Meta's **test** number, and a Meta app has only one webhook URL.
- **How:** create a separate Meta app for the test number. WhatsApp → Configuration → Webhook: Callback URL `https://api-staging.veriprops.ng/api/webhooks/whatsapp`, Verify token = `preview`'s `WHATSAPP_BUSINESS_WEBHOOK_VERIFY_TOKEN`, then subscribe to the **`messages`** field (it carries both customer messages and delivery/read receipts). The app's **App secret** (App settings → Basic) goes in `preview` as `WHATSAPP_APP_SECRET_KEY`; it checks every delivery's signature. Add your test handsets to the test number's allowed recipients. Set `WHATSAPP_OFFICIAL_NUMBER` in `backend/.env.staging` to the test number; today it still opens the production number.

**C6. DeepSeek credit (the WhatsApp bot's understanding of free text).**

- **What:** `INTENT_API_KEY` is set, but DeepSeek answers `402 Payment Required`: the account has no credit.
- **Why:** every free-text bot message falls back to "let me get a person", so the bot looks alive but can't help.
- **How:** platform.deepseek.com → Billing → top up.
- **Done when:** `doppler run --project veriprops-verf-backend --config preview -- python scripts/live_smoke.py --only intent` prints PASS.

## D. The deploy pipeline

**D1. Confirm the sweep Worker runs.**

- **What:** `SWEEP_TRIGGER_SECRET` is in Doppler `dev`, `preview` and `prd`, and the Cloudflare repo secrets are set. The last deploy (PR #28, 2026-10-09) failed only at `deploy-sweep-cron`, because those secrets were added afterwards; nothing has deployed since.
- **Done when:** after the next push, Cloudflare → Workers → `veriprops-sweep-cron-<env>` → Logs shows a 200 every minute.

**D2. Confirm the staging Doppler tokens point at `preview`.**

- **What:** the GitHub `staging` Environment holds `DOPPLER_TOKEN_BACKEND` / `DOPPLER_TOKEN_FRONTEND` (set 2026-07-16). A token can't be read back, so check where it came from.
- **How:** Doppler → each project → `preview` → Access → Service Tokens: a token created on 2026-07-16 should be listed. If not, generate a read-only one there and run `gh secret set DOPPLER_TOKEN_BACKEND --env staging` (and `_FRONTEND`).
- **Done when:** a push to `staging` deploys green and `https://staging.veriprops.ng` loads.

**D3. Confirm `APP_DOMAIN`.** `backend/.env.prod` has `APP_DOMAIN=https://api.veriprops.ng`. Confirm it's the real backend address, then drop its `FIXME(ops)`.

## E. Payment gateways

**E1. Register the gateway webhooks.**

- **Why:** a customer's payment only becomes "PAID" when the gateway calls us back. Without the webhook, paid cases sit unpaid forever.
- **How:**
  - Flutterwave dashboard (**live** mode) → Settings → Webhooks → URL `https://api.veriprops.ng/api/webhooks/flutterwave`, Secret hash = the `FLUTTERWAVE_WEBHOOK_SECRET` value in Doppler `prd`. Tick the boxes to receive webhooks for failed payments and for transfers.
  - Paystack dashboard (**live** mode) → Settings → API Keys & Webhooks → Live Webhook URL `https://api.veriprops.ng/api/webhooks/paystack`. Paystack signs with the secret key; there's nothing else to set.
  - Do the same in each gateway's **test** mode with `https://api-staging.veriprops.ng/api/webhooks/<gateway>` (Flutterwave secret hash = `preview`'s `FLUTTERWAVE_WEBHOOK_SECRET`).
  - Use the `api.*` hosts, **not** `https://veriprops.ng/...`: the bare domain answers with a redirect to `www`, and gateways don't follow a redirect on a POST. Leave the dashboards' redirect/callback URL fields empty; the app sends a return URL with every payment.
  - Full list of URLs and values per environment: section J.
- **Also:** email Flutterwave support asking them to **enable chargeback webhooks** on the account. They're off by default, and without them a disputed card payment never reaches the admin console.

**E2. Paystack transfer OTP.**

- **Why:** with it on, every agent payout waits for an OTP typed into the Paystack dashboard, so automated payouts stall.
- **How:** Paystack → Settings → Preferences → Transfers → turn off "Confirm transfers before sending" (OTP).

**E3. Decide the Flutterwave IP whitelist.**

- **What:** Flutterwave can be told to accept transfer requests only from listed server IPs.
- **Why it's a decision:** Vercel doesn't have fixed outgoing IPs, so a whitelist would block our payouts at random.
- **Recommendation:** leave the whitelist **off** while we're on Vercel (the secret key still guards it), and turn it on after the planned move to Docker hosting with a fixed IP.

## F. Checks on staging once A, C and E are done

The full runbook is `docs/live-integration-smoke.md`.

1. Run the smoke script from `backend/`:

   ```
   doppler run --project veriprops-verf-backend --config preview -- python scripts/live_smoke.py --email <your inbox> --phone <+234 handset> --intl-phone <non-Nigerian handset> --whatsapp <digits> --selfie <a photo of your face>
   ```

   It must exit 0. Exit 3 means some probe was skipped, so the run doesn't count.
2. Run the browser spec from `frontend/` with `UAT_BASE_URL=https://staging.veriprops.ng` + the admin credentials + `UAT_LIVE_SELFIE`: `pnpm e2e:live`. It pays with the sandbox card, checks the report PDF, and checks the reviewer's side-by-side KYC photos.
3. Confirm that Termii delivers to a number sent as digits only (no `+`). If it doesn't, tell Claude: the SMS adapter needs a one-line change.
4. Send a test broadcast from the admin console. Within a few minutes the Worker's ticks should move it from SENDING to SENT.
5. Record each result in the third-party register in `docs/progress.md`.
6. What the smoke run needs from you: an inbox you can read, a Nigerian handset (`+234…`), a non-Nigerian handset, a JPEG of your face (delete it afterwards), and your WhatsApp number on the test number's allowed recipients. Optional: a Paystack test bank account (`--paystack-bank code:number`).

## G. WhatsApp launch (the code is done; these are the external steps)

Follow `docs/whatsapp-launch-runbook.md` in order. Its number-binding step **cannot be undone**.

- Meta business verification + green tick.
- Approval of all seven message templates (the admin console's template registry shows their status).
- Custody of the number +2349167624347.
- A staff rota for the chat console during service hours, and the `support_hours_*` settings in the admin config set to match it.
- Counsel sign-off on the chat-retention period (part of A5).
- Then do the security checklist in `docs/handoff-token-pen-check.md`.

## H. Business and legal sign-offs before taking real money (MASTER-PRD §G.3)

- Final tier prices: today's ₦50k / ₦120k / ₦300k and all money defaults are placeholders.
- The limitation-of-liability clause (1× fees cap). **This blocks paid go-live.**
- NBA counsel sign-off + lawyer professional-indemnity cover, before `LEGAL_OPINION_ENABLED` is turned on.
- The admin staffing commitment ("N admins can handle M verifications a day").
- The legal basis for keeping data after an erasure request.
- Whether the Nigeria-court clause is enforceable abroad (per market, later).

## I. Housekeeping

- Optional: set `NEXT_PUBLIC_MICROSOFT_CLARITY_PROJECT_ID` if you want Clarity analytics. Foreign-currency quotes use fixed placeholder rates (`PRICING_FX_PROVIDER=STUB`); that's a decision for later, not a key to buy.

## J. Reference: URLs and values per environment

Copy these into the providers' dashboards. **Dev** runs payments, Dojah, storage and WhatsApp on stubs, so it needs none of the third-party entries below.

**Hosts**

| | Staging | Production |
| --- | --- | --- |
| Website | `https://staging.veriprops.ng` | `https://veriprops.ng` (redirects to `https://www.veriprops.ng`) |
| Backend API (webhooks go here) | `https://api-staging.veriprops.ng` | `https://api.veriprops.ng` |
| Doppler config | `preview` | `prd` |

Every webhook is `<backend API>/api/webhooks/<provider>`: a GET for the provider's verification handshake, a POST for each delivery. Point webhooks at the backend API host, never the website: the bare `veriprops.ng` redirects, and providers don't follow a redirect on a POST.

**Webhooks to register**

| Provider | Dashboard place | Staging URL | Production URL | Secret / token, and where it lives |
| --- | --- | --- | --- | --- |
| Flutterwave | Settings → Webhooks (test mode for staging, live mode for production) | `https://api-staging.veriprops.ng/api/webhooks/flutterwave` | `https://api.veriprops.ng/api/webhooks/flutterwave` | "Secret hash": any random string you choose; the same value goes in Doppler `FLUTTERWAVE_WEBHOOK_SECRET`. Tick failed-payment and transfer webhooks; ask support to enable chargeback webhooks. |
| Paystack | Settings → API Keys & Webhooks → Test / Live Webhook URL | `https://api-staging.veriprops.ng/api/webhooks/paystack` | `https://api.veriprops.ng/api/webhooks/paystack` | None to set: Paystack signs with `PAYSTACK_SECRET_KEY`. |
| WhatsApp (Meta) | App → WhatsApp → Configuration → Webhook; subscribe to the `messages` field | `https://api-staging.veriprops.ng/api/webhooks/whatsapp` (the test number's own Meta app) | `https://api.veriprops.ng/api/webhooks/whatsapp` | "Verify token": any random string; the same value in `WHATSAPP_BUSINESS_WEBHOOK_VERIFY_TOKEN`. The app's App secret (App settings → Basic) in `WHATSAPP_APP_SECRET_KEY`. |

Leave the payment dashboards' redirect/callback URL fields empty: the app sends its own return URL with every payment.

**Providers with no webhook to register:** Termii, Twilio, Resend, Mailjet, SES, Google Places, Cloudflare R2. **Dojah** has a Developers → Webhooks page, but its events cover the KYC widget, SMS, address and AML monitoring, which Veriprops doesn't use; leave it empty (A1 step 5). If any dashboard asks for a webhook URL, leave it blank.

**Sign-in redirect URIs (Google)** — APIs & Services → Credentials → the OAuth client → Authorized redirect URIs:

- `https://veriprops.ng/api/users/auth/oauth/google/callback`
- `https://staging.veriprops.ng/api/users/auth/oauth/google/callback`
- `https://dev.veriprops.ng/api/users/auth/oauth/google/callback`
- `http://localhost:3000/api/users/auth/oauth/google/callback`

They must match exactly, including the bare `veriprops.ng`: that's the address the app sends (`OAUTH_CALLBACK_BASE_URL` in `backend/.env.prod`).

**Doppler keys per provider** (backend project; staging = `preview`, production = `prd`)

| Provider | Keys | Where to find the values |
| --- | --- | --- |
| Dojah | `DOJAH_APP_ID`, `DOJAH_PRIVATE_KEY` | app.dojah.io → your app → App ID and Secret Key (sandbox keys for `preview`, live keys for `prd`). Host is set in the env files: `https://sandbox.dojah.io` (staging), `https://api.dojah.io` (production). |
| Cloudflare R2 | `STORAGE_ENDPOINT_URL`, `STORAGE_ACCESS_KEY_ID`, `STORAGE_SECRET_ACCESS_KEY` | Endpoint `https://<account id>.r2.cloudflarestorage.com` (account id on the R2 overview page). Keys from R2 → Manage API tokens (Object Read & Write, one bucket). Buckets: `veriprops-documents-staging`, `veriprops-documents-prod`. |
| Flutterwave | `FLUTTERWAVE_PUBLIC_KEY`, `FLUTTERWAVE_SECRET_KEY`, `FLUTTERWAVE_WEBHOOK_SECRET` | Settings → API Keys (test keys for `preview`, live for `prd`); the webhook secret is the "Secret hash" you set above. |
| Paystack | `PAYSTACK_PUBLIC_KEY`, `PAYSTACK_SECRET_KEY` | Settings → API Keys & Webhooks (`pk_test`/`sk_test` for `preview`, `pk_live`/`sk_live` for `prd`). |
| WhatsApp | `WHATSAPP_BUSINESS_ACCESS_TOKEN`, `WHATSAPP_APP_SECRET_KEY`, `WHATSAPP_BUSINESS_WEBHOOK_VERIFY_TOKEN`, `WHATSAPP_HANDOFF_PRIVATE_KEY`, `WHATSAPP_HANDOFF_PUBLIC_KEY`; staging also `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_BUSINESS_ACCOUNT_ID` | System User permanent token; App settings → Basic → App secret; your chosen verify token; the keypair from A4. Production's number id and WABA id are already in `backend/.env.prod`; staging's (the test number's) come from WhatsApp → API Setup. |
| Twilio | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER` | Console home → Account Info; the number from Phone Numbers → Active numbers. |
| Termii | `TERMII_API_KEY` | Termii dashboard → API settings. Sender ID `veriprops`. |
| Email | `RESEND_API_KEY`, `MAILJET_API_KEY`, `MAILJET_API_SECRET`, `AWS_ACCESS_KEY`, `AWS_SECRET_ACCESS_KEY` (SES only) | Resend → API Keys; Mailjet → Account → API Keys; AWS IAM user with `ses:SendEmail`. Sender `noreply@veriprops.ng`. |
| Google | `GOOGLE_CLIENT_SECRET`, `GOOGLE_PLACES_API_KEY` | Credentials → the OAuth client's secret; the Places key (API restriction: Places API (New) only; application restriction: None). |
| DeepSeek (WhatsApp bot) | `INTENT_API_KEY` | platform.deepseek.com → API keys. **The account has no credit** (it answers `402 Payment Required`, so every bot message goes to a person): top it up under Billing. |
| Sweep Worker | `SWEEP_TRIGGER_SECRET` | Any random string; the deploy copies it into the Cloudflare Worker. |
| Edge auth | `EDGE_AUTH_SECRET` (backend **and** frontend projects, same value) | Any random string; the same value in the Cloudflare Transform Rule that injects `x-edge-auth` (already in place). |

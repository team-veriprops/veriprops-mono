 # This Captures things to note about this project
1. Agents must specify their availability to receive tasks.
2. Run app wide audit to verify guidelines were followed.
3. Fix Oauth session cookie issue

# Test Users
Seeded QA logins come from `POST /api/dev/seed` (its response payload lists them); never record passwords here.

# Pending owner actions (checked 2026-10-09)

**Background you need.**
- Veriprops deploys from GitHub Actions only (`.github/workflows/deploy.yml`):
  - push to `dev` → dev
  - push to `staging` → staging
  - push to `master` → production
- Each deploy runs the tests, then the database migrations, then the backend, the frontend and the Cloudflare "sweep" Worker.
- Secrets are not in git. They live in **Doppler**: project `veriprops-verf-backend` (and `veriprops-verf-frontend`), one config per environment (`dev`, `stg`, `prd`).
- The pipeline reads Doppler through the GitHub **Environment** secrets `DOPPLER_TOKEN_BACKEND` / `DOPPLER_TOKEN_FRONTEND`.
- Production checks its own settings at start-up (`backend/main/app/config/settings.py`, `_enforce_live_integrations_in_production`) and **refuses to start** if a required key is missing, naming every missing key in one error.

To generate any random secret below:
`python -c "import secrets; print(secrets.token_urlsafe(48))"`

## A. Do first: production cannot start on its next deploy

**A1. Fix the AWS key name in Doppler `dev` and `prd`.**
- **What:** Doppler holds `AWS_ACCESS_KEY_ID`, but the app reads `AWS_ACCESS_KEY` (`settings.py:178`; used by S3 uploads and SES email).
- **Why:** under the wrong name, production stops at start-up with `AWS_ACCESS_KEY is not set`. Dev runs, but every S3 upload fails.
- **How:** Doppler → `veriprops-verf-backend` → config `prd` → add a secret named `AWS_ACCESS_KEY` with the same value as `AWS_ACCESS_KEY_ID` → Save. Repeat for `dev`. Delete `AWS_ACCESS_KEY_ID` afterwards; nothing reads it.
- **Done when:** `doppler secrets get AWS_ACCESS_KEY --project veriprops-verf-backend --config prd --plain` prints a value.

**A2. Add the missing production keys to Doppler `prd`.** Missing today:
- `GOOGLE_PLACES_API_KEY` (address autocomplete; required at start-up)
- `SWEEP_TRIGGER_SECRET` (see B2; required at start-up)
- `INTENT_API_KEY` (the DeepSeek key the WhatsApp bot uses to classify messages)
- `FIREBASE_CREDENTIALS_JSON_B64` and `GOOGLE_SERVICE_ACCOUNT_JSON_B64` (see A3)

- **Why:** the first two stop production from starting. Without the intent key the WhatsApp bot can't understand messages. Without the Firebase key push notifications fail.
- **How:** Doppler → `prd` → Add Secret for each.
  - Places key: from Google Cloud console → APIs & Services → Credentials.
  - Intent key: from your DeepSeek account → API keys.
- **Done when:** the next production deploy's "Deploy backend" step is green and `https://api.veriprops.ng/` answers.

**A3. Rotate the two Google service-account keys.**
- **What:** the Firebase key (push) and the "contracts" Google key (Drive/Docs) were once committed to git under `backend/service_accounts/`. The files are now untracked, but they remain in git history, which we chose not to rewrite.
- **Why:** anyone with a copy of the repo history holds working credentials to the Google project.
- **How:**
  1. console.cloud.google.com → IAM & Admin → Service accounts → open the Firebase Admin SDK account → Keys → Add key → JSON (downloads a file).
  2. On the same page, delete the old key.
  3. Do the same for the contracts account.
  4. Encode each file on one line: Git Bash `base64 -w0 key.json`.
  5. Put the Firebase output in Doppler as `FIREBASE_CREDENTIALS_JSON_B64` and the other as `GOOGLE_SERVICE_ACCOUNT_JSON_B64`, in `dev`, `stg` and `prd`.
  6. Delete the downloaded files.
- **Done when:** the Keys tab of both accounts shows only the new key.

## B. The deploy pipeline

**B1. Merge PR #28 (`fix/pending-issues` → `dev`).**
- **What:** the 9-stage pending-issues fix. CI is green on all 13 checks.
- **Why:** until it merges, dev runs the old code and the database stays at migration 0007.
- **How:** GitHub → Pull requests → #28 → Merge. Then Actions → the "Deploy" run for `dev` → the "Run database migrations" step must show `0007 … → 0013_d97_config_rows`.
- **Expect** the `deploy-sweep-cron` job to fail until B3 is done. It doesn't block the app.

**B2. `SWEEP_TRIGGER_SECRET` in every environment.**
- **What:** a shared password between the backend and the Cloudflare Worker that runs the scheduled jobs every minute (payout batches, SLA checks, broadcast sending, retries).
- **Why:**
  - Without it, the endpoint answers 404 and **no scheduled job ever runs**.
  - Production and staging refuse to start without it.
- **How:** generate one value per environment (a different value each). Add it as `SWEEP_TRIGGER_SECRET` in Doppler `dev`, `stg` and `prd`. The deploy copies it into the Worker for you.
- **Done when:** Cloudflare → Workers → `veriprops-sweep-cron-<env>` → Logs shows a 200 every minute.

**B3. Cloudflare repo secrets.**
- **What:** two GitHub repository secrets that let `deploy.yml` publish the Worker.
- **Why:** without them the `deploy-sweep-cron` job fails on every push and the jobs never run in deployed environments.
- **How:**
  1. Cloudflare dashboard → My Profile → API Tokens → Create Token → template "Edit Cloudflare Workers" → limit it to the Veriprops account → create, and copy the token.
  2. The Account ID is on the right side of any zone's Overview page.
  3. Then:
     ```
     gh secret set CLOUDFLARE_API_TOKEN
     gh secret set CLOUDFLARE_ACCOUNT_ID
     ```
     Each command prompts you to paste the value.
- **Done when:** `gh secret list` shows both, and the next deploy's `deploy-sweep-cron` job is green.

**B4. Branch protection on `dev`, `staging`, `master` (none exists today).**
- **Why:** anyone with push access can push straight to `master`. That deploys to production and runs migrations without review or CI.
- **How:** GitHub → repo Settings → Branches → Add classic branch protection rule. For each of the three branch names:
  - tick "Require a pull request before merging";
  - tick "Require status checks to pass", search `summary` and add **only** `Pull Requests / summary`. Any other check is skipped when no relevant files changed, and a required skipped check blocks merging forever;
  - leave "Allow force pushes" and "Allow deletions" off.
- **Done when:** `gh api repos/team-veriprops/veriprops-mono/branches/master/protection` no longer says "Branch not protected".

## C. Staging (the human-QA environment) does not exist in Doppler yet

**C1. Create the Doppler `stg` configs.**
- **What:** Doppler has `dev`, `dev_personal`, `dev_test`, `preview` and `prd`, but **no `stg`**, in both projects. The GitHub `staging` Environment already holds `DOPPLER_TOKEN_*` secrets, but they can't point at a `stg` that doesn't exist.
- **Why:** a push to `staging` either fails or runs against the wrong configuration.
- **How:**
  1. Doppler → `veriprops-verf-backend` → add an environment named "Staging", slug `stg`. Its root config is `stg`.
  2. Copy the key **names** from `prd`: `doppler secrets --project veriprops-verf-backend --config prd --only-names`.
  3. Fill `stg` with **sandbox/test** values, not production ones:
     - `APPODUS_ACTIVE_ENV=staging`
     - `AUTHJWT_SECRET_KEY` (new random; staging refuses a placeholder)
     - `EDGE_AUTH_SECRET` (new random, and used in E1)
     - `SWEEP_TRIGGER_SECRET`
     - the database credentials
     - `FLUTTERWAVE_SECRET_KEY` (`FLWSECK_TEST-…`), `FLUTTERWAVE_PUBLIC_KEY`, `FLUTTERWAVE_WEBHOOK_SECRET`
     - `PAYSTACK_SECRET_KEY` (`sk_test_…`), `PAYSTACK_PUBLIC_KEY`
     - `DOJAH_APP_ID`, `DOJAH_PRIVATE_KEY` (sandbox app)
     - `GOOGLE_PLACES_API_KEY`
     - `AWS_ACCESS_KEY`, `AWS_SECRET_ACCESS_KEY` (a separate staging bucket + IAM user)
     - `RESEND_API_KEY`, `MAILJET_API_KEY`, `MAILJET_API_SECRET`
     - `TERMII_API_KEY`
     - `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`
     - `WHATSAPP_BUSINESS_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_BUSINESS_ACCOUNT_ID` (Meta's free **test** number)
     - `INTENT_API_KEY`, `GOOGLE_CLIENT_SECRET`, `SUPER_ADMIN_PASSWORD`
  4. In `veriprops-verf-frontend` create `stg` too, with `EDGE_AUTH_SECRET` (same value as the backend's) and the two `NEXT_PUBLIC_*` keys `prd` has.
  5. In each project: Access → Service Tokens → generate a read-only token for `stg`. Then:
     ```
     gh secret set DOPPLER_TOKEN_BACKEND --env staging
     gh secret set DOPPLER_TOKEN_FRONTEND --env staging
     ```
- **Done when:** a push to `staging` deploys green, and `https://staging.veriprops.ng` loads.

**C2. Staging file fixes (a small PR; these are public values, so they belong in git).**
- `backend/.env.staging:53` `WHATSAPP_OFFICIAL_NUMBER` still carries a placeholder. Until it's the Meta test number, staging's "Chat on WhatsApp" links open the **production** number.
- `backend/.env.staging:93` and `backend/.env.prod:78`: `FACEBOOK_APP_ID=mock_value`. Facebook login can't work until this holds the real app id (developers.facebook.com → your app → App ID). The app secret goes in Doppler as `FACEBOOK_APP_SECRET`; `prd` has it, and `stg` needs it.
- Apple sign-in: `APPLE_TEAM_ID`, `APPLE_CLIENT_ID` and `APPLE_KEY_ID` still default to `mock_value` (`appodus_utils/config/settings.py:229-231`).
  - Set the real values in `.env.prod` / `.env.staging`. They come from developer.apple.com → Certificates, IDs & Profiles: Team ID; the Services ID; the Sign in with Apple key's Key ID.
  - `APPLE_PRIVATE_KEY` (the .p8 contents) goes in Doppler. `prd` has it, and `stg` needs it.
- `backend/.env.prod:18`: confirm `APP_DOMAIN=https://api.veriprops.ng` is the real backend address. Links in emails and webhooks are built from it.

## D. Payment and Google providers

**D1. Register the gateway webhooks.**
- **Why:** a customer's payment only becomes "PAID" when the gateway calls us back. Without the webhook, paid cases sit unpaid forever.
- **How:**
  - Flutterwave dashboard → Settings → Webhooks → URL `https://veriprops.ng/api/webhooks/flutterwave`, plus the secret hash = the `FLUTTERWAVE_WEBHOOK_SECRET` value in Doppler.
  - Paystack dashboard → Settings → API Keys & Webhooks → Webhook URL `https://veriprops.ng/api/webhooks/paystack`. Paystack signs with the secret key; there's nothing else to set.
  - Do the same in each gateway's **test** mode with `https://staging.veriprops.ng/api/webhooks/<gateway>`.
- **Also:** email Flutterwave support asking them to **enable chargeback webhooks** on the account. They're off by default, and without them a disputed card payment never reaches the admin console.

**D2. Paystack transfer OTP.**
- **Why:** with it on, every agent payout waits for an OTP typed into the Paystack dashboard, so automated payouts stall.
- **How:** Paystack → Settings → Preferences → Transfers → turn off "Confirm transfers before sending" (OTP).

**D3. Decide the Flutterwave IP whitelist.**
- **What:** Flutterwave can be told to accept transfer requests only from listed server IPs.
- **Why it's a decision:** Vercel doesn't have fixed outgoing IPs, so a whitelist would block our payouts at random.
- **Recommendation:** leave the whitelist **off** while we're on Vercel (the secret key still guards it), and turn it on after the planned move to Docker hosting with a fixed IP.

**D4. Restrict the Google Places key.**
- **Why:** an unrestricted key that leaks can be used for any Google API, billed to us.
- **How:** Google Cloud console → APIs & Services → Credentials → the Places key → API restrictions → "Restrict key" → tick only **Places API (New)** → Save. Leave application restrictions at "None": the key is used only server-side, from Vercel's changing IPs.

## E. Cloudflare edge auth

**E1. Confirm the `x-edge-auth` Transform Rule.**
- **What:** Cloudflare adds a secret header (`x-edge-auth: <EDGE_AUTH_SECRET>`) to every request it forwards. The backend and the frontend reject requests without it. That stops people bypassing Cloudflare through the raw `*.vercel.app` addresses.
- **Why:** Doppler `dev` and `prd` already hold `EDGE_AUTH_SECRET`, so both apps already **enforce** it. If the rule is missing for a hostname, that hostname answers 403 to everyone.
- **How:** Cloudflare → the `veriprops.ng` zone → Rules → Transform Rules → Modify Request Header → a rule matching all hostnames (`veriprops.ng`, `www`, `api`, `dev`, `api-dev`, `staging`, `api-staging`) → Set static header `x-edge-auth` = that environment's `EDGE_AUTH_SECRET` from Doppler. Use one rule per environment if the values differ.
- **Done when:** each site loads through its normal address, and `curl -I https://<project>.vercel.app/` answers 403.

## F. Checks on staging once C and D are done
The full runbook is `docs/live-integration-smoke.md`.
1. Run the smoke script from `backend/`:
   ```
   doppler run --project veriprops-verf-backend --config stg -- python scripts/live_smoke.py --email <your inbox> --phone <+234 handset> --intl-phone <non-Nigerian handset> --whatsapp <digits> --selfie <a photo of your face>
   ```
   It must exit 0. Exit 3 means some probe was skipped, so the run doesn't count.
2. Run the browser spec from `frontend/` with `UAT_BASE_URL=https://staging.veriprops.ng` + the admin credentials + `UAT_LIVE_SELFIE`: `pnpm e2e:live`. It pays with the sandbox card, checks the report PDF, and checks the reviewer's side-by-side KYC photos.
3. Confirm that Termii delivers to a number sent as digits only (no `+`). If it doesn't, tell Claude: the SMS adapter needs a one-line change.
4. Send a test broadcast from the admin console. Within a few minutes the Worker's ticks should move it from SENDING to SENT.
5. Record each result in the third-party register in `docs/progress.md`.

## G. WhatsApp launch (the code is done; these are the external steps)
Follow `docs/whatsapp-launch-runbook.md` in order. Its number-binding step **cannot be undone**.
- Meta business verification + green tick.
- Approval of all seven message templates (the admin console's template registry shows their status).
- Custody of the number +2349167624347.
- A staff rota for the chat console during service hours.
- Counsel sign-off on the chat-retention period. Until then the three WhatsApp legal documents stay `DRAFT`.
- Then do the security checklist in `docs/handoff-token-pen-check.md`.

## H. Business and legal sign-offs before taking real money (MASTER-PRD §G.3)
- Final tier prices: today's ₦50k / ₦120k / ₦300k and all money defaults are placeholders.
- The limitation-of-liability clause (1× fees cap). **This blocks paid go-live.**
- NBA counsel sign-off + lawyer professional-indemnity cover, before `LEGAL_OPINION_ENABLED` is turned on.
- The admin staffing commitment ("N admins can handle M verifications a day").
- The legal basis for keeping data after an erasure request.
- Whether the Nigeria-court clause is enforceable abroad (per market, later).

## I. Housekeeping
- Delete the leftover folder `.claude/worktrees/audit-remediation`. Git no longer tracks it as a worktree, so it's only clutter; delete it in Explorer. If Windows complains about long paths: `git -c core.longpaths=true clean -fdx .claude/worktrees`, or `Remove-Item -Recurse -Force`.

# Live integration smoke — the release gate for third parties

CI and the e2e suite run every third party on its stub: no payment gateway, Dojah, Google, S3, SMS, email or WhatsApp call ever leaves an automated run. The respx/Stubber contract tests hold each adapter to the provider's **documented** shapes. This runbook covers the last step: calling the real sandboxes with staging's keys. It is the step that catches a misnamed field, a signature keyed wrongly, or an answer read the wrong way.

Run it:

- before the first release that turns an integration on;
- after any change to an adapter;
- whenever a provider announces an API change.

A release does not reach `master` until both parts pass on staging.

The live status of every integration is tracked in the third-party register in [progress.md](progress.md#third-party-sandbox-test-register). Update a row to `SANDBOX-PASSED` once it passes here.

## The two parts

| Part | What it proves | Where |
| --- | --- | --- |
| `live_smoke.py` | Each adapter against its sandbox. It opens a checkout and reads back the unpaid charge; lists banks, resolves an account, quotes a fee and (optionally) sends ₦100; puts, reads and deletes an object on S3; sends an email on each of Resend, Mailjet and SES, one SMS each on Termii and Twilio, and a WhatsApp template; checks five intents; runs Dojah liveness and a BVN match; and gets Places suggestions and details | [backend/scripts/live_smoke.py](../backend/scripts/live_smoke.py) |
| `@live` Playwright spec | What only a browser on the deployment can show. A customer pays on the hosted checkout with the sandbox card, the webhook makes the case PAID, and failing the case refunds the charge. The report PDF renders on the deployed runtime. The reviewer sees the applicant's selfie and passport photo side by side, loaded from private storage | [frontend/e2e/specs/live-integrations.spec.ts](../frontend/e2e/specs/live-integrations.spec.ts) |

## Before the first run (one-time setup)

1. **Doppler `stg` exists.** Create the `stg` config in `veriprops-verf-backend` (and `veriprops-verf-frontend`), then put its service tokens in the GitHub `staging` Environment. `deploy.yml` needs them as well.
2. **Sandbox keys in Doppler `stg`.** A missing key makes only its own probe SKIP, never fail:
   - **Payments:** `FLUTTERWAVE_SECRET_KEY` (`FLWSECK_TEST-…`), `FLUTTERWAVE_PUBLIC_KEY`, `FLUTTERWAVE_WEBHOOK_SECRET`, `PAYSTACK_SECRET_KEY` (`sk_test_…`), `PAYSTACK_PUBLIC_KEY`.
   - **Identity and address:** `DOJAH_APP_ID`, `DOJAH_PRIVATE_KEY` (sandbox app), `GOOGLE_PLACES_API_KEY`.
   - **Storage:** `AWS_ACCESS_KEY`, `AWS_SECRET_ACCESS_KEY` (staging bucket `AWS_S3_BUCKET`, plus SES in the same region).
   - **Email and SMS:** `RESEND_API_KEY`, `MAILJET_API_KEY`, `MAILJET_API_SECRET`, `TERMII_API_KEY`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`.
   - **WhatsApp and intent:** `WHATSAPP_BUSINESS_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_BUSINESS_ACCOUNT_ID` (Meta's test number), `INTENT_API_KEY`.
3. **Gateway dashboards (test mode):**
   - Register the webhook URLs: `https://staging.veriprops.ng/api/webhooks/flutterwave` and `https://staging.veriprops.ng/api/webhooks/paystack`. Like every call, they go through the Next.js proxy (production: `https://veriprops.ng/api/webhooks/<gateway>`).
   - On Paystack, turn off the transfer OTP.
   - On Flutterwave, whitelist the calling IP for transfers. Vercel's outbound IPs change, so settle this before relying on live payouts.
4. **Meta:** add your handset to the test number's allowed recipients.
5. **Test assets:**
   - an inbox you can read;
   - a Nigerian handset for Termii, and a non-Nigerian one for Twilio;
   - a JPEG of a real face, which Dojah's liveness check requires. Use your own, keep it out of git, and delete it after the run.

## Part 1 — the smoke script

Run it from `backend/`, on your machine. It refuses to start under a production environment, with a live gateway key, or against Dojah's production host.

```bash
doppler run --project veriprops-verf-backend --config stg -- \
  python scripts/live_smoke.py \
    --email you@example.com \
    --phone +2348030000000 --intl-phone +447700900000 \
    --whatsapp 2348030000000 \
    --selfie ~/face.jpg \
    --paystack-bank 058:0123456789   # a Paystack test account, if you have one
```

- `python scripts/live_smoke.py --list` names every probe. `--only places,dojah` runs a subset.
- `--send-transfer` actually sends ₦100 on each transfer gateway. It also confirms that a second transfer under the same reference is refused. Without the flag, the transfer probes stop after quoting the fee.
- Each line is `PASS`, `FAIL` or `SKIP` with its reason. The run exits 0 only when every selected probe passed, 1 on any `FAIL`, and 3 when a probe was skipped: a skipped probe proves nothing about its integration, so a run with skips is incomplete, never green.
- Confirm the messages that were accepted actually arrived: the email in the inbox, the SMS on each handset, and the WhatsApp template.

Things to look for, and to record in the register, on the first run:

- **Dojah.** Which name fields `/kyc/nin/verify` returns. How an unknown number is answered: a 404, or a 400 containing "not found". Both are handled, and anything else surfaces as a FAIL.
- **Termii.** Whether it accepts the number with its leading `+`. The adapter sends E.164 as given.
- **Paystack.** Whether the webhook signature validates with the secret key.
- **Both gateways.** Whether a second refund of an already-refunded charge is declined.
- **Flutterwave.** What the fee quote says, compared with the fee the dashboard shows as charged.

## Part 2 — the `@live` browser spec

The spec runs against the deployed staging, on one Chromium worker with no retries, because a retry would pay and upload a second time. It never resets or seeds staging, which human QA shares. Each test builds its own case and accounts through `/dev/scenario`. Those accounts' emails (`@veriprops.io`) and phones (`+234 8100…`) are QA fixture addresses. On staging the messaging router hands every message to them to a sink that records it and sends nothing, so a run's notifications (payment confirmed, report ready, new job) reach no one. A tester whose own number happens to start `+234 8100` gets no SMS on staging.

```bash
cd frontend
UAT_BASE_URL=https://staging.veriprops.ng \
UAT_LIVE_ADMIN_EMAIL=<staging SUPER_ADMIN_EMAIL> \
UAT_LIVE_ADMIN_PASSWORD=<staging SUPER_ADMIN_PASSWORD> \
UAT_LIVE_SELFIE=/path/to/face.jpg \
pnpm e2e:live
```

- **UAT-LIVE-01 (payment and refund).**
  1. The spec follows whichever gateway staging's `ACTIVE_PAYMENT_METHOD` chose, and pays with that gateway's documented sandbox card: Flutterwave 5531 8866 5214 2950 / 09/32 / 564, PIN 3310, OTP 12345; Paystack 4084 0840 8408 4081 / any future expiry / 408.
  2. It waits up to 3 minutes for the webhook to make the case PAID.
  3. The admin then fails the case. The admin's confirmation says "Verification failed & refunded" only when the gateway took the refund; a refusal says so, and waits in Finance's refunds-to-retry list.
  4. To try the other gateway, switch `ACTIVE_PAYMENT_METHOD` in Doppler `stg`, redeploy, and run again.
  - **The card-filling steps are unverified until the first run.** They find each field by what a person reads (its label, placeholder or name, in the page or any frame), because the gateways' pages are theirs and change without notice. If a gateway changes its checkout, the trace shows the step that stopped; fix the patterns in [e2e/helpers/live.ts](../frontend/e2e/helpers/live.ts).
- **UAT-LIVE-02 (report PDF).** The released report downloads as a real PDF rendered on the deployed runtime.
- **UAT-LIVE-03 (KYC photos).**
  1. An applicant applies with a passport, with your face as the selfie. Dojah runs liveness, and then the application waits for a reviewer.
  2. The admin opens the application.
  3. The spec checks that both photos load from their short-lived storage links and that the divider moves.
  - This is the only check of the reviewer view with real photos. Locally, stub storage serves placeholder links.

A test missing its admin credentials or selfie **fails** and names the variable. A skipped live test would prove nothing, and the lane also fails if it finds no tests at all.

When a test fails, the HTML report and the trace are in `frontend/e2e/playwright-report/live`.

## After a run

- Update each row you exercised in the [register](progress.md#third-party-sandbox-test-register): `SANDBOX-PASSED` with the date, or `BLOCKED(<reason>)`.
- Delete the selfie file.
- The sandbox charges, transfers and applications stay on staging, where they are harmless. S3 objects written by the smoke are deleted by the run itself.

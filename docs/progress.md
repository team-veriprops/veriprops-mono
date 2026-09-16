# Progress Tracker — Playwright UAT suite (cycle 3)

status: **Slice 0 passed. Slice 1 is partial.** All changes are uncommitted, pending user approval.

## Slice 0 — baseline gate (existing 5 specs × 6 projects)
- **Stack:** backend `dev_personal` on :8000. Frontend is the **production standalone build** (`node .next/standalone/server.js` on :3001) behind Caddy TLS on :3000 ([e2e/tls/Caddyfile](../frontend/e2e/tls/Caddyfile)). See uat-strategy §9.
- **chromium-desktop:** 24/24 on first attempt, after the fixes below.
- **Full matrix:** 144 tests (24 × 6 projects), **143 passed first attempt, 0 failed**, 1 retry, 23.3 min.
  - The retry was UAT-WAH-01 on chromium-mobile. Its setup POST `/dev/whatsapp/handoff-token` got a 502 because Caddy logged `dial tcp …:3001: i/o timeout` twice: Docker Desktop's container→host hop stalled. The request never reached Next or the backend, and the next mint (5 s later) succeeded.
  - Environment, not the app. Fix: the Caddyfile retries failed dials within 15 s (`lb_try_duration`, `dial_timeout 10s`); a failed dial was never sent, so this is safe for POST.
  - The matrix was **not re-run** after that Caddyfile change.
- **Every retry, and what caused it:**
  - **UAT-AUTH-05:** three causes, all fixed.
    - The spec logged in before the reset request had completed; it now waits for `?reset=ok`.
    - A wrong-password 401 triggered a session refresh, so login showed "Session refresh failed". `FetchHttpClient` now skips the refresh without a refresh cookie and surfaces the original error; UAT-AUTH-03 asserts the message via `login-error`.
    - Caddy reused an upstream socket Node had closed after its 5 s keep-alive, so the POST got a bare 502. The Caddyfile now sets `keepalive 2s`.
  - **UAT-DEV-02:** the home pricing section hydrated with a mismatch, because the server rendered static prices and the client the backend's. Prices are now fetched on the server via `lib/public-config.server.ts` and the shared `lib/backend-fetch.server.ts`; the static figures are deleted.
  - **UAT-GP-01:** `next dev` compiled the route on first visit. The suite now runs against the production build.
  - **UAT-WA-01:** the home page's `load` event waited on Google Fonts and a Google-hosted hero image.
    - Fonts are self-hosted via `next/font` (`lib/fonts.ts`).
    - The hero image is committed at `public/assets/hero-property.png` and preloaded via `next/image`.
    - `goto()` waits for `domcontentloaded`, then `__app_ready__`.
- **SEO pass (user requirement: every UI decision is SEO-optimized):**
  - The pricing tiers now carry `pricingJsonLd` (a schema.org Service with one NGN Offer per priced tier), built from `withLivePrices`, the same helper the pricing section renders from.
  - Verified in the served HTML: backend prices, 3 Offers, no third-party font/image hosts, font and hero preloads.
- **Gates:** Vitest 593/593, `tsc` and eslint clean. Backend unit 2066/2066 (`/dev/scenario` work); ruff and mypy clean.

## Slice 1 — foundation (code complete; browser pass pending)
- **`/dev/scenario`:** stages `DRAFT` → `RELEASED` are cumulative. `DISPUTED`, `RECHECK_REQUESTED` and `PAYOUT_READY` are alternative branches off `RELEASED`, all driven by the real services.
  - The only direct write is `PAYOUT_READY` backdating the commission `clearing_until`, before the real clearance sweep runs.
  - Live check: 12/12 builds OK. DISPUTED returns a dispute id; PAYOUT_READY gives every agent a positive balance and a bank account on both tiers.
  - The `customer` option is deferred (user decision) until a spec needs a shared customer.
- **Seed:**
  - one restricted admin per `AdminSubRole` (OPERATIONS/FINANCE);
  - login credentials for every agent and admin in the payload;
  - 12 paging verifications across 4 statuses, as rows.

  Live check: all 6 seeded admins and agents sign in with the returned credentials.
- **Frontend:**
  - `DataTable` testids (`datatable-row`/`data-row-id`, `-row-actions`, `datatable-action-{slug}`, `-prev`/`-next`) come from `components/ui/table/testIds.ts`.
  - `DetailDrawer` is now a labelled modal dialog, with `detail-drawer`/`detail-drawer-close`.
- **Browser suite plumbing:**
  - `e2e/fixtures.ts`: persona pages, `scenario`/`pageFor`, `sweep`, `wa`, `mail`.
  - `helpers/ui.ts`: `tableRow`, `rowAction`, `drawer`, `expectForbidden`, `stubPay`, `downloadAndRead`.
  - Config: `fullyParallel` with `UAT_WORKERS`. `@P0` runs on 6 engines, `@P1`/`@P2` on chromium-desktop + webkit-mobile. `@serial` specs run in chained single-worker `<engine>-serial` projects; UAT-DEV-04, UAT-AUTH-05 and UAT-GP-01 are tagged.
  - `global-setup` logs in every persona from seed credentials. `agentEmail`/`QA_PASSWORD` are removed.
- **Deferred:** evidence fixture files, until the first evidence-upload spec (Slice 4).
- **Gates:** backend unit 2093/2093, ruff and mypy clean. Frontend Vitest 607/607 (before the testIds refactor; component tests re-run 7/7), tsc and eslint clean. `playwright --list` split: 138 tests.
- **First chromium-desktop pass (4 workers): inconclusive, but it surfaced three real problems.** The machine was saturated (100% CPU, 0.7 GB of 7.8 GB free) because a full Vitest run overlapped it. Result: 11 passed, 8 flaky, 3 failed, 3 not run; most first attempts timed out after 1–2 min.
  - **Real defects on the pay page**, first seen because scenario customers are first-time customers (the seeded customer never sees these):
    - `CountryCodeSelect`'s flag-only trigger had no accessible name (axe `button-name`, critical). It now carries an `aria-label`, with a test.
    - The first-time-discount line failed contrast (`text-emerald-600`); it's now `emerald-700`.
  - **Config flaw:** the `@serial` lane was chained with project dependencies, which skip dependants on any failure, so all 3 serial tests "did not run". Replaced by `e2e/run-lanes.mjs`: two invocations (`UAT_LANE=parallel`, then `UAT_LANE=serial` on one worker, reusing the seed). The serial lane always runs, and either lane failing fails the run.
  - UAT-AUTH-07 (stuck on "Loading devices…") and UAT-WAH-01 (stuck on the loading placeholder) failed both attempts. Their page snapshots show loading states, not errors, which fits starvation. To be confirmed on a rerun with 2 workers.
- **chromium-desktop rerun (2 workers, both lanes):**
  - **Parallel lane:** 21/22 first attempt. UAT-AUTH-07 and UAT-WAH-01 pass, confirming starvation.
  - **Serial lane:** 3/3, and it ran despite the parallel failure, so the runner works.
  - **UAT-GP-02 failed both attempts on two more real a11y defects**, visible only once the OTP is sent and the number is locked. The earlier two are confirmed fixed.
    - The shared toast close button was unnamed. It now has `aria-label="Close"`.
    - `PhoneInputWithCountry` dimmed its whole locked field with `opacity-50`, putting the "+234" dial code at 2.48:1 contrast. The input now shows the locked state itself; tested.
- **chromium-desktop rerun after those fixes (2 workers, both lanes): 25/25 on first attempt, no retries.** Parallel lane 22/22; serial lane 3/3.
- **Full 6-engine matrix (2 workers, both lanes, after commit `c38a053`):** parallel lane 118/120 on first attempt, serial lane 18/18, **0 failures**, 2 retries.
  - Both retries were UAT-GP-02 on firefox-desktop and firefox-mobile: `page.goto(pay page)` failed with `NS_BINDING_ABORTED`.
  - Cause (spec helper race): `loginViaUi` returned as soon as the session was authenticated, while the login form was still redirecting into the portal. The spec's next navigation raced that redirect; Firefox cancels the losing navigation, Chromium didn't. The failure snapshot shows the portal dashboard.
  - Fix: `loginViaUi` also waits until the page has left `/auth` and the destination reports ready. This hardens every caller: `global-setup`, UAT-AUTH-05, `pageFor`.
- **Firefox rerun after the `loginViaUi` fix (firefox-desktop + firefox-mobile, both lanes):** 44/44 on first attempt (parallel 38, serial 6), no retries. Slice 1 is green across the 6-engine matrix.

## Slice 2 — session lifecycle (`session.spec.ts`, P0)
- **Scenarios** (each builds its own customer, so all run parallel):
  - UAT-SESS-01: an expired access token is renewed silently.
  - UAT-SESS-02: a lost session goes to login and back to the page.
  - UAT-SESS-03: a device revoked elsewhere gets "Your session has expired", then login. Access tokens live out their 15-min TTL per PRD §3/§7.2, so the spec clears the access-cookie pair to stand in for expiry.
  - UAT-SESS-04: sign-out via the desktop user menu or the mobile drawer.
- **Testids:** `user-menu`, `user-menu-signout`, `sidebar-open`, `sidebar-signout`. The `signOut(page)` helper picks the layout.
- **Real defects found and fixed (test-first):**
  - **Revoked-session login loop (backend).** A rejected refresh called `unset_jwt_cookies()` and then *raised*. The exception handler renders a fresh response, so the cookie deletions were dropped. The frontend proxy still saw a refresh cookie, bounced `/auth/login` back to the dashboard, got another 401, and redirected to login again, endlessly. The refresh now *returns* the 401 via the new shared `exception_json_response`, with the deletions on it. The test asserts the real `Set-Cookie` headers; the old test mocked `authorize` and so passed while the bug was live.
  - **Password hashing blocked the event loop (backend).** Argon2 ran synchronously in login, signup, reset and set-password, stalling every concurrent request, including other users' silent refreshes. New `Utils.hash_password`/`check_password` use `asyncio.to_thread`, like the other blocking integrations. Dev fixtures hash the shared QA password once.
  - **Three SSE connections per tab (frontend).** The chat, notification and earnings hooks each opened `/api/chat/stream` and retried independently on a broken session. `lib/userStream.ts` now shares one connection per tab, fanning out to subscribers, with the same retry budget.
  - Together, the last two caused SESS-01's retries: its refresh never answered within 15 s.
- **Runner fix:** `run-lanes.mjs` passes `--pass-with-no-tests`, so a filtered run with nothing for one lane doesn't fail.
- **Spec-side lessons:**
  - Change session cookies from `about:blank`: an open portal page reacts to the change and races the test's navigation.
  - Both sign-out entry points are always in the DOM, so wait for the visible one.
  - A dropdown clicked before it is interactive only focuses the trigger, so retry the open while closed.
  - The expired-session dialog redirects after 1.5 s, so it is not axe-scanned (known a11y gap on a transient dialog). The login page it lands on is scanned.
- **Result on chromium-desktop + webkit-mobile after the fixes:** 8/8 on first attempt, each test 12–25 s (previously 30–90 s).
- **Full-suite 6-engine run (2 workers, both lanes):** parallel lane 140 passed, 2 flaky, **2 failed**; serial lane 18/18.
  - **UAT-SESS-04 (chromium-mobile) — real app defect.** The mobile drawer stays mounted and slides off-screen, so while closed its links and sign-out remained focusable and clickable outside the viewport (Playwright: "visible, enabled and stable … outside of the viewport"; a keyboard or screen-reader user could land in hidden navigation). The drawer is now `inert` while closed. Its close button gained `sidebar-close`, and `signOut` retries opening until sign-out is in the viewport — the same pre-hydration race as the desktop dropdown.
  - **UAT-SESS-03 (chromium-desktop) — load, not a defect.** It failed twice in the matrix (snapshots still on the dashboard; the retry timed out inside `loginViaUi`) but passed on every other engine, and passes in 41.3 s when run alone on an idle machine.
  - **Flaky (both load, not defects):** UAT-DEV-02 (webkit-mobile) waited 20 s for `__app_ready__` then passed in 8.2 s; UAT-WA-01 (chromium-desktop) waited for the widget then passed in 19.9 s. 144 tests × 2 workers on one 8 GB box.
- **Second look at UAT-SESS-04 — the failure was the helper, not the drawer.** The `inert` change is still right on its own merits (a closed drawer must not hold focusable, clickable controls off-screen), but it did not fix the test. A closed drawer's contents keep a layout box, so Playwright reports `sidebar-close` as *visible* even while the drawer is parked off-screen; the helper's "already open?" check therefore never clicked the toggle (19 polls, sign-out at viewport ratio 0). The toggle only ever opens, so the helper now clicks it on every attempt and waits for sign-out to be **in the viewport** — visibility is not openness for a transform-based drawer.
- **UAT-SESS-03's dialog assertion was racy.** The expired dialog hands off to login after ~1.5 s, so on a fast machine the redirect wins and the dialog is gone before the assertion runs. The spec now checks its wording only while it is still on screen, and always asserts the login handoff, which is the outcome that matters.
- **A retry once ran 13.8 min.** It died in setup: `POST /dev/scenario` hit the API client's 120 s timeout under load. A fixture's pending request is not capped by the 90 s test timeout — worth remembering when a "hung" test appears.
- **Rerun after those fixes (chromium-desktop + chromium-mobile):** 8/8 on first attempt, 11–39 s each, no retries — including UAT-SESS-04 on chromium-mobile, the case that had failed twice.
- **Same spec on firefox-desktop/mobile + webkit-desktop/mobile:** 16 tests, 14 passed on first attempt, 2 flaky, 0 failed. **UAT-SESS-04 passes on all six engines**, so the drawer fix holds on every layout.
  - Both retries were firefox-desktop's first two tests, running together off a cold browser start: each hit the 90 s *test timeout* rather than failing an assertion (SESS-01 still waiting on `devices-list`; SESS-02 killed mid-fill as its page was torn down). Both passed on retry in ~30 s.
  - SESS-01's symptom is the same one the hashing/SSE fixes addressed. It has not recurred on any other engine or run, so this reads as cold-start slowness on the slowest engine — worth watching rather than treating as closed.
- **Slice 2 gates:** backend unit 2096/2096, ruff + mypy clean; frontend Vitest 615/615, tsc + eslint clean.

## Slice 3 — signup funnel (`auth.spec.ts` extended, P0/P1)
- **Scenarios** (each signs up a brand-new account, so they own their data and run in parallel):
  - UAT-AUTH-09: the four-step funnel (Account → Verify → Residence → Consent) ends on the new-verification wizard, because a new customer has no verification yet.
  - UAT-AUTH-10: a half-finished signup resumes, restoring the typed email.
  - UAT-AUTH-11: signing up through a **real** referral code (read from `/referrals/me`) costs the invitee nothing. The referrer's credit only exists after the invitee's first payment clears the chargeback window, so that assertion belongs to the referral spec — not faked here with an API check.
  - UAT-AUTH-12: `?intent=agent` lands in the agent portal with the AGENT persona.
  - UAT-AUTH-13: every step is scanned for a11y, including the OTP dialog while open.
  - UAT-AUTH-14: a password set at `/auth/set-password` is the one that then signs the user in.
- `auth.spec.ts` now imports from `../fixtures`, and its two free `"CUSTOMER"`/`"AGENT"` literals are `UserPersona` members.
- **Testids:** `verify-{email,phone}-{input,send,verified,error}` (parameterised, so the OAuth profile modal gets them too), `verify-otp-{modal,digit-N,confirm,cancel,resend,error}`, `signup-{country,timezone,currency-CODE,residence-*,consent-*,resumed}`.
- **This stack runs `PHONE_VERIFICATION_ENABLED=false`**, so the Verify step asks for one OTP (email) and collects the phone for the pay step. The spec uses the same `verify-phone-input` id on both sides of the flag, so it survives the flag flipping.

### Real app defects found and fixed (test-first)
- **Unlabelled selects — axe `select-name`, critical.** The residence step's country and timezone selects had no accessible name: the local `Field` rendered a `<label>` with no `htmlFor` and the selects carried no id. Screen-reader users heard two unnamed dropdowns. The sibling text inputs escaped the equivalent rule only because axe accepts their `placeholder` as a name — selects have no such fallback.
  - The same defect sat in `ProfileCompletionModal` (the OAuth twin of this step), and `AdminPayouts`' status filter was unnamed too.
  - Fixed by extracting shared [`Field`/`FieldGroup`](../frontend/src/components/ui/form/Field.tsx), which hands the control the id its label points at so the binding cannot be forgotten. That removed **three** duplicated local `Field` copies (residence, account basics, profile modal). `FieldGroup` names the currency button row via `role="group"` + `aria-labelledby`, since there is no single control to bind. `FormField`/`FormSelect` were not reusable here — they require `useFormContext`, and these steps use plain `useForm`.
- **Credentials written into the URL on a pre-hydration submit.** UAT-AUTH-14 caught `/auth/set-password?password=…&confirmPassword=…`: before React attaches `onSubmit`, the browser submits the form itself, and with no `method` that is a GET — putting the password in browser history, the `Referer` header and Caddy's access log. Every credential form in the app was built this way (login, signup basics, reset, forgot, account password).
  - Fixed with [`SubmitButton`](../frontend/src/components/ui/form/SubmitButton.tsx) — disabled until hydrated, which also blocks implicit Enter-key submission — plus `method="post"` on the eight auth forms as defence in depth. Hydration is detected with `useSyncExternalStore` ([`useHydrated`](../frontend/src/hooks/useHydrated.ts)); the obvious `setState`-in-effect version is banned by this repo's React Compiler lint.
  - `renderToStaticMarkup` *is* the pre-hydration HTML, so the guard test asserts directly that the server never ships a live submit.
  - **`__app_ready__` cannot protect against this.** It is set by a `useEffect` on the root provider, so it means "the app mounted", not "this form is interactive" — the app has to own the fix.

### Misjudgements of mine, recorded so they are not repeated
- **The a11y scan raced an animation.** UAT-AUTH-13's first failure was `color-contrast 2.16` on an OTP box whose style was `opacity: 0` — axe scanned mid-stagger. The helper now waits for the last box to reach full opacity. Same class as the Slice 2 overlay race.
- **I under-budgeted the OTP wait, twice.** UAT-AUTH-09 failed on four engines against a 15 s then a 45 s budget. The funnel describes are now `test.slow()` and the dialog wait is 90 s; re-verified green on the three engines that had failed (24.9–35.7 s). The cause is the browser being starved under two workers on this box — **not** a slow endpoint, as the corrected measurement below shows.
- **I misdiagnosed it as rate limiting first.** `otp_send` is capped at 5/min/IP, which fit the symptom — but a truncated grep let me read "no hit in `.env.dev_personal`" as "not set", when that file does set `DISABLE_RATE_LIMITING=true`. Throttles were off the whole time. A truncated search is not evidence of absence.
- The helper now races the dialog against `verify-{field}-error` and fails with the app's own message, so a refused send can never again present as a bare "element not found".

### Corrected: the OTP endpoint is **not** slow — my measurement was wrong
- I first recorded "requesting an OTP takes 3–12 s", blamed the in-band mail dispatch, and wrote that into the Slice 3 commit message. **It was an artifact of how I measured.** Benchmarked properly — one warm process, connection setup absorbed first, eight sequential sends — `POST /users/auth/otp/send` runs in **0.14–0.25 s** (control `GET /config/public`: 0.04–0.06 s).
- Every earlier probe was a *first* call in a freshly spawned PowerShell process or `Start-Job` runspace, and the first call to a host costs ~2.3 s in connection setup plus backend lazy-init (the DI lookup and first Jinja compile inside `send_verification_msg`). I sampled that warm-up five times and read it as endpoint latency, including a "concurrent" test whose two runspaces each paid it separately.
- **Lesson: absorb the first-call cost before timing anything, and measure inside one process.** Two conclusions in this slice (this one and the rate-limit theory) came from treating a single unrepresentative sample as evidence.
- The in-band dispatch in `_send_direct_message` is therefore fine as it stands: ~0.15 s buys the persist-before-send guarantee.
- Still worth knowing: `send_verification_msg` swallows delivery failures with only a log warning, so a genuinely broken send would show the user neither a dialog nor an error. Not hit here, and not changed.
- **Watch item:** UAT-AUTH-03 on webkit-mobile once timed out after 20 s waiting for `login-submit` to become enabled — the cost side of disabled-until-hydrated, under two-worker load. It passed on retry in 9.7 s. Worth watching; the alternative re-opens the credentials-in-URL hole.

### Results
- **All six engines green**, assembled from chunked runs (a full matrix in one invocation exceeds the per-run time budget on this box): chromium-desktop 13/13, chromium-mobile 9 P0, webkit-desktop 9 P0, webkit-mobile 13/13, firefox-desktop 9 P0, firefox-mobile 9/9 first attempt.
- **`@serial` lane: 6/6** — UAT-AUTH-05 passes on every engine.
- The final edits were timeout-only (`test.slow()`, 90 s dialog wait) and so cannot invalidate the earlier passes; they were re-verified on the three engines that had failed.
- **Slice 3 gates:** frontend Vitest 623/623, tsc + eslint clean; backend ruff + mypy clean, unit 2109/2109 (the backend was touched by the follow-on below).

## Slice 3 follow-on — telling the truth about an undelivered code
Both fixes came from reading the OTP path while chasing a latency problem that turned out not to exist.

- **A failed OTP send was invisible to the customer.** `MessagingService.send_bulk` *buckets* failures into its result rather than raising, and `_send_direct_message` discarded that result — so a send that failed on every channel was indistinguishable from one that succeeded. `send_otp` returned 200, the dialog opened, and the customer waited for a code that had never been sent.
  - Best-effort delivery is deliberate **and tested** (`test_a_failing_fallback_never_propagates`: "the code is already stored, and raising here would turn an undelivered message into a failed API call"), so the fix is additive rather than a reversal: `_send_direct_message` returns its `BulkSendResult`, the three verification senders pass it through, and `send_verification_msg` reports `delivered` without ever raising.
  - `send_otp` now answers with an `OtpSendResultDto`, which also closes a contract drift: the endpoint returned a raw dict, so the wire key was literally `resend_in` while the frontend's type claimed `resendIn`. Nothing read it, so the mismatch had gone unnoticed.
  - A shared `otpDeliveryError` helper drives all three surfaces that request a code — the signup verify step, the OAuth profile modal, and the §10.5 pay gate — so none of them can read a 2xx as "the code is on its way".
- **`IntegrationException` could not be rendered at all.** It never called `super().__init__`, so it carried no `status_code`/`code`; raised across a request boundary it would fail *inside* `appodus_exception_handler` and return an unmapped 500. It now carries a 502 envelope, with 429 for the rate-limit subclass and 422 for validation. (`Exception.__new__` had always populated `args`, so `str(exc)` looked right and the gap stayed hidden — the provider tests match on message text and still pass.)
- **Another spec mistake of mine:** four `waitForURL` calls used Playwright's default `waitUntil: "load"`, which waits on every image and font — precisely what `goto()` avoids. UAT-AUTH-14 timed out on it once; all four now use `domcontentloaded`, and the set-password describe is `test.slow()` like the funnel describes.
- **Verified:** backend ruff + mypy clean, unit **2109/2109**; frontend Vitest **623/623**, tsc + eslint clean; `auth.spec.ts` **13/13 on chromium-desktop, first attempt, no retries**.
- **Worth knowing for the next slice:** the backend does not hot-reload. A stale process serves the old contract and fails the funnel in a way that looks like a code defect — the verification run now polls until `/otp/send` actually returns `delivered` before it starts testing.

### Decisions carried into Slice 4 (user, 2026-09-16)
- **The 6-engine matrix is not re-run for the follow-on.** chromium-desktop 13/13 stands as its verification, and full-matrix confirmation folds into Slice 4's checkpoint — so that run covers both slices' specs. Recorded rather than assumed: the follow-on's engine risk is low because it changed a JSON field and a navigation option, not rendering.
- **Slice 4 is next:** golden-path legs 2–5 (`golden-path.spec.ts`, `@serial`) — customer pays → admin suggests/assigns → agents accept, start, upload and submit → admin rejects FIELD → the agent sees the reason and resubmits → approve with quality → release → the customer sees the REPORT_READY bell, the disclaimer gate, the trust gauge and a parsed PDF (`%PDF` + VID). Folds in the assign/suggest testids.
- **Stack at handover:** backend on :8000 restarted and confirmed serving the new `OtpSendResultDto`; standalone frontend on :3001 from the current production build; Caddy TLS on :3000. `dev` is at `52d09ea`.

---

# Progress Tracker — WhatsApp Channel (cycle 2)

status: **cycle complete** — S1–S11 delivered (+ S4.1 template registry, + S10.0 handoffs)

## Completed Slices
- S1 widget + attribution (dc7adb4)
- S2 channel foundation (webhook + facade + console inbound)
- S3 handoff tokens + /wa/* landings
- S4 OTP account linking (E1) + number lifecycle
- S4.1 §26.7 Meta template registry + S4 follow-up defects
- S5 bot engine core (intent facade, guardrails, status flow, admin console mode + hand-back)
- S6 resumable chat intake + payment handoff (586de9c)
- S7 console outbound adapter (WA-12/WA-41) + Meta's 24-hour window + §26.6.3 non-text policy
  (WA-06/WA-38) (3c53bd2)
- S8 dual consent (WA-27), event-driven milestones (WA-16/WA-34), report delivery (WA-35)
- S9 slim per-case delegates (WA-26) (72ef8a9)
- **S10.0 reachable pay/report handoffs (WA-17)** — unplanned; §26.3.4 marks three actions
  `HANDOFF` and only `upload` had a producer, so `/wa/pay/<token>` and `/wa/report/<token>`
  were built, tested and unreachable from a conversation (be32c7a)
- **S10 channel analytics (WA-43)** (634d0ef)
- **S11 live hardening & launch-gate closeout (WA-40, WA-42, WA-44; WA-02 code-side)**
- **S12 closeout pass** — the §26 incorporation plus the loose ends S11 left:
  - PRD.md's standalone §7 spec folded into **MASTER-PRD §26** (subsections 26.1–26.11), and
    every `§7.x` reference in the repo resolved. `§7.x` had meant *three* things at once —
    MASTER-PRD §7 (Auth), the legacy v2.4 Phase 7 (Agent Task Execution, now §11.3/§11.4/§12.x),
    and the channel — so ~1,420 references across 268 files were disambiguated, not just
    renamed. §G gained the WhatsApp rows, including the `google_drive` marker that had been
    unpaired since D83.
  - **A stale consent literal in both e2e harnesses.** Migration 0011 moved PLATFORM_TERMS and
    PRIVACY_POLICY to `1.1.0`; the harness still signed `1.0.0`, so every drive-through customer
    was created already owing the two consents it had just accepted. Versions now come from
    `GET /users/auth/consents/documents`, and each signup asserts it owes nothing afterwards.
  - **§26.8 compliance is now proven live, not just mocked** — the consent ledger exporting in
    the §19.3 pack, erasure reaching the five channel tables, and the erased number reading as a
    stranger to the bot on its next message. 470 checks, up from 445.
  - Defect fixes: a bare `raise` in the callback service that threw `RuntimeError: No active
    exception to reraise` instead of a 404; two silently-swallowed `AttributeError`s; dead
    commented-out blocks. The unreachable frontend upload cluster (mock service, offline queue,
    six `ui/upload` components and an unregistered service worker) was deleted.

## Current Slice
- none

## Pending Slices
- none — the cycle's code-side scope is complete. What remains is external (§26.11 hard gates)
  and is tracked in [whatsapp-launch-runbook.md](whatsapp-launch-runbook.md).

## Runtime State
- idle (checkpointed after S11)

## Pending Recovery
- none

## Blockers
- none in code. Launch is gated on the external §26.11 items — Meta business verification,
  template approval, number custody, counsel sign-off on retention duration.

## Findings outside the WhatsApp scope
- `appodus_utils/domain/webhook/google_drive/` is **dead and does not import**: `repo.py`,
  `service.py` and `validator.py` reference `main.app.domain.webhook.google_drive.*` and
  `main.app.db.repo`, neither of which exists, so only `model.py` loads — and it registers a
  `g_drive_webhook_subscriptions` table with no migration builder. Nothing in the app's import
  graph reaches it, so it is inert rather than broken in production.
  **Resolved as D83 (2026-09-03): kept and marked**, not deleted — it is vendored code outside
  this cycle's scope. The greppable `TODO(gap):` is on `model.py`, and its paired
  "Known Gaps & Roadmap" row landed with the §26 incorporation (MASTER-PRD §G.2), so
  `grep -rn "TODO(gap)"` enumerates every deferred item again.

## Open Questions
- none (gate decisions D42–D48; run-time decisions D49–D86)

## What later work should know
- **All seven §26.7 templates have senders**, and all three §26.3.4 `HANDOFF` actions now have
  producers. What remains external is Meta's **approval** of each template, which the admin
  registry displays and which deliberately never blocks a send — a stale sync must not take the
  channel down. Confirm at the live smoke that the approved `otp_auth` button matches the shape
  we send.
- The §26.4.4 SMS fallback is wired (D60, amending D46): a failed WhatsApp send falls back to SMS
  on the same number through the router's existing Termii → Twilio chain.
- Migrations 0002–0011 are applied and round-tripped against live Postgres.
- **The §26.3.2 projection now has three consumers**: the status flow, §26.6.3's uploadable-case
  filter, and S10.0's pay/report eligibility. The last one is the subtle case —
  `ChannelState.REPORT_READY` projects from `UNDER_REVIEW`, where the report exists but has not
  passed the §8 release gate, so only `DELIVERED` may be offered a report link.
- §26.4.6's **marketing** consent is captured and stored from day one but gates nothing: there
  are no marketing templates at v1 (P1 drafts them only when a campaign exists). §26.10 now
  reports its opt-in rate, which is the number that says how big a Marketplace launch audience
  would be (D84).
- §26.9's delegate enhancements (multiple delegates, granular permissions) are untouched by
  design — `GET /verifications/{id}/delegates` already returns a list, so the shape survives.
- **Deploying the §26.8 copy asks every existing account to re-accept.** The three documents move
  to consent version `1.1.0`, which is the correct NDPA answer for a new cross-border transfer
  disclosure and a visible UX event on the day. Retention *duration* is still counsel's call, so
  the clauses name the policy rather than a number and all three stay `DRAFT`.

## Launch-gate checklist (§26.11)
Full runbook, with owners and order: [whatsapp-launch-runbook.md](whatsapp-launch-runbook.md).
The one-way step (concierge → Cloud API number binding) is called out there.

- [ ] ⊘ Meta Business verification approved; green tick granted
- [~] All §26.7 templates approved — all 7 declared, bodied, **sent by real code paths**, and
      visible in the admin registry with Meta-synced status; submission and approval external
- [ ] ⊘ Number custody confirmed and documented (+2349167624347)
- [x] Fraud-scan pipeline verified against WhatsApp-sourced messages (drive-through evidence)
- [~] Token pen-check — automated coverage green; the human/proxy items remain
      (docs/handoff-token-pen-check.md)
- [x] Failure fallback **tested**, not just implemented — `POST /dev/whatsapp/fail-next-turn`
      makes one real turn fail and the drive-through asserts the §26.6.5 apology, the human
      promise in whichever shape Decision G's coverage gives, the `BOT_PIPELINE_FAILED` admin
      alert, the one-shot reset, and the §26.10 `PIPELINE_FAILURE` count
- [~] ToS + privacy policy updated per §26.8 — clauses live at consent version `1.1.0`;
      counsel sign-off on **retention duration** outstanding, and the documents stay `DRAFT`
      until it lands
- [ ] ⊘ Console rota covering G1 hours (must match `support_hours_*` in `system_config` — the
      bot quotes those numbers to customers)
- [ ] ⊘ Concierge → Cloud API cutover scheduled (number binding is one-way)
- [ ] ⊘ Conversation-theme tracker live from first concierge chat

## Risks
- Meta platform dependency (accepted, §26.11). Early warning is now instrumented: §26.10 reports
  the quality rating with its sync age, and `YELLOW` is the signal to slow template volume.
- Template-approval lag (mitigation: the registry shipped early, in S4.1).
- Live-path external assets (D43 fallback: the stub keeps everything demoable, and
  `ENVIRONMENT=prod` refuses to boot on it).

## Last Commit
- S11: live-path hardening and launch-gate closeout

## Completion %
- 100 of the cycle's code-side scope (11 of 11 slices, plus S4.1 and S10.0).
  42 of 44 requirements complete; WA-02 and WA-41 are `partial` **only** on external Meta items.

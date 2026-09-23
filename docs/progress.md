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

## Slice 4 — golden path legs 2-5 (`golden-path.spec.ts`, P0, `@serial`)

**UAT-GP-03**, one ordered journey through the browser: an admin opens the ranked-suggestions
panel and assigns all three STANDARD roles → each agent accepts, starts, captures evidence and
submits their findings → the admin returns the FIELD task with a reason → that agent reads it,
resumes the work and resubmits → the admin approves each role with a quality score and releases →
the customer is notified, clears the disclaimer gate, reads the trust gauge and VID, and downloads
the branded PDF (asserted on the bytes: `%PDF` magic plus the VID). Four a11y scans en route.

### Six defects it exposed, each fixed test-first
1. **An admin-assigned task could not be accepted.** `assign()` moves a task to ASSIGNED and out
   of the pool, but both agent surfaces gated Accept on `state === PENDING || inPool`. The
   manual-assign path (§2.2) therefore dead-ended in the UI while the backend's machine allowed
   ASSIGNED → ACCEPTED all along. (`AgentTaskList`, `AgentTaskDetail`.)
2. **A returned task could not be reworked.** `reject_task` lands the task in REJECTED, and
   `TASK_TRANSITIONS[REJECTED] = {IN_PROGRESS}` — which is exactly what `start()` performs. But the
   screen offered Start only for ACCEPTED, so the agent saw the reason their work came back and had
   no way to act on it. Now REJECTED offers "Resume work", and the reason card carries an anchor.
3. **Three unnamed or unbound controls on the admin console**, all blocking axe: `delay-days` had a
   `<Label>` bound to nothing, the `note-category` Radix trigger had no accessible name, and the
   task-progress bar was an unnamed progressbar. Inputs bound with `useId()`; Radix triggers named
   with `aria-label`, following the Slice 3 `AdminPayouts` precedent (a `<label for>` pointing at a
   `<button role="combobox">` names nothing).
4. **The review decision never reached the browser.** `approve_task` deliberately leaves the task
   SUBMITTED and records `review_decision` (§8.3) — but both hand-written mappers
   (`review/controller.py:_task_dto` and `admin/service.py:_task_dto`) omitted it, and the read
   `TaskDto` never declared it. An admin approving a task got no confirmation their review had
   registered. The service test passes because it stops short of the mapper; the new
   `test_review_task_dto.py` covers both mappers and the camelCase wire key. Frontend `TaskDto`
   gained the field, so `AdminReportReview` dropped the `as { reviewDecision?: string }` cast it
   had been reading through.
5. **The trust band failed WCAG AA on every band** — measured 3.50:1 (Safe), 2.83:1 (Caution) and
   4.48:1 (High Risk) against the tinted panel, where AA needs 4.5:1. The scan only caught Safe,
   because that is the band this scenario happened to produce. Fixed as one shared
   `lib/trust-band.ts` expressed in the theme's semantic tokens (5.06 / 5.23 / 6.07), which also
   removed the duplicate band→colour tables that `ReportView` and `PublicSummaryCard` each kept
   privately — two surfaces required to stay in §10.2 parity and free to drift.
6. **The findings block was unreachable by keyboard** (`max-h-32 overflow-auto` with nothing
   focusable inside). Only chromium-mobile exposed it: on a desktop viewport the same JSON fits and
   nothing scrolls. This is the clearest argument this cycle for the engine matrix being a gate
   rather than a formality.

### Misjudgements of mine, recorded so they are not repeated
- **I traded one strict-mode violation for another.** After the bell resolved to three elements I
  scoped it with `filter({ visible: true })`, which passed on desktop and broke on mobile: the
  off-canvas drawer's copy still reads as *visible* while parked off-screen. `helpers/ui.ts:signOut`
  documents that exact trap in a comment I had already read. The locators now scope to the page
  header, which holds the one bell the customer is looking at on any viewport.
- **I nearly went hunting for a backend defect that did not exist.** When the bell assertion failed
  I suspected `REPORT_READY` had no in-app rule, since the rule row declares only email/SMS/WhatsApp.
  `NotificationRule.in_app` defaults to `True`; the notification was always being created, and the
  page snapshot showed the badge reading 7. The failure was entirely my locator.

### Folded in
- Assign/suggest anchors (`assign-submit-{role}`, `suggested-agent-{role}` + `data-agent-id`),
  `open-task-{id}`, `detail-rejection-reason`, `task-progress`, `report-trust-score`.
- The deferred evidence fixtures now exist and are used: `e2e/fixtures/evidence-photo.jpg` (a real
  JPEG; the backend hashes and stores bytes without validating mime or size) and `evidence-doc.pdf`.
- `src/test-utils/markup.ts` — testid-anchored markup assertions shared by the new component tests.
  `Field.test.tsx` keeps its own local helper: it reads the first attribute in the document, which
  is right for a single-control render and wrong for a page.
- Fixture contexts now grant geolocation, so evidence capture exercises the real §12.3 GPS path
  instead of waiting out a prompt for a position it would never get.

### Verification
- **Gates:** backend ruff + mypy clean, unit **2260**; frontend Vitest **684** across 106 files,
  tsc + eslint clean.
- **chromium-desktop + chromium-mobile:** green on both `auth.spec.ts` and `golden-path.spec.ts`
  (24/24 parallel lane, 6/6 serial lane), first attempt.
- **webkit:** parallel lane 24/24 in 2.9 min; serial lane **timed out on UAT-GP-03** (both engines,
  attempt and retry) and took 21 min. Classified **environment, not defect**: the captured page
  shows all three tasks Approved with a projected score of 95 and *no* "approve every task to
  enable release" hint, so `releasable` was true and the button live — the release round-trip
  simply had not finished inside the 15s assertion default. WebKit runs this journey several times
  slower than Chromium here, and release is its heaviest action (composite score, commissions, the
  versioned report, event fan-out). The budget is now stated outright: `test.setTimeout(600_000)`
  for the journey and 60s for the release assertion, replacing `test.slow()`'s 270s.
- **firefox:** parallel lane **20/20** in 9.3 min. Serial lane 5/6 — firefox-desktop UAT-GP-03
  failed waiting on `Evidence (1)`: 15s after the file was set the screen still read `Evidence (0)`,
  i.e. the upload had not landed. **Timing, not incompatibility** — firefox-mobile is the same Gecko
  engine and passed the identical flow. Evidence capture waits on the browser's GPS hint (§12.3),
  posts a multipart body and re-reads the list, so that assertion now carries a 60s budget like
  release. This box ran the Firefox serial lane in **1.4 hours**, ~9x Chromium per test.
- Both widened budgets are about this machine, not the product: every assertion still fails loudly
  if the outcome never arrives; it simply waits long enough for a slow engine to get there.
- **Re-verified against the new budgets:** webkit-mobile green on the first attempt (5.8 min);
  webkit-desktop and firefox-desktop green **on retry** (8.3 min / 3.5 min), their first attempts
  exceeding even the 600s budget. Those three tests alone took 1.7 hours here.

### Matrix result
| engine | `auth.spec.ts` + `golden-path.spec.ts` |
|---|---|
| chromium-desktop | green, first attempt |
| chromium-mobile | green, first attempt |
| webkit-mobile | green, first attempt |
| firefox-mobile | green, first attempt |
| webkit-desktop | green; UAT-GP-03 needed a retry |
| firefox-desktop | green; UAT-GP-03 needed a retry |

**All six engines pass UAT-GP-03; two need a retry.** That is short of this plan's "no unexplained
retries" bar, and the explanation is machine speed rather than product behaviour — the evidence for
that reading is recorded above (the release button live with `releasable` true, and firefox-mobile
passing the identical flow on the same Gecko engine). **User decision, 2026-09-22: this stands as
it is** — the journey is not made cheaper, the budget is not raised again, and GP-03 is not
re-tagged to fewer engines. CI hardware is unmeasured, so if the retries survive there the
classification deserves re-testing rather than restating.
- A full six-engine matrix in one invocation exceeds the per-call budget here, so it is chunked by
  engine pair.

### Stack notes for the next session
- **The local database was rebuilt as `veriprops_uat`.** After the squash that folded the
  unified-chat chain into `0001_initial_schema`, `veriprops_local` was left stamped at
  `0011_whatsapp_legal_copy` — a revision that no longer exists, so alembic could not resolve it.
  The migration's own docstring states the invariant: a squash is only safe once every live database
  is stamped at the head being folded in. Rather than drop anything, a fresh database was created
  and migrated to `0017_session_pkey_name`; `veriprops_local` is untouched. The backend is started
  with `DB_NAME=veriprops_uat`, which takes precedence over the env file, so no config was edited.
- The backend does not hot-reload, and the standalone frontend serves a built bundle: after any
  source change both must be restarted (and the frontend rebuilt + restaged) before a browser run
  means anything.

## Slice 5 — agent onboarding + both persona doors (`agent-onboarding.spec.ts`, P1)

**UAT-AGENT-01…05.** The compulsory §3.1 gate and the application wizard (roles → KYC → credentials
→ review), an admin approving in the drawer, a failed BVN rejected *with its reason shown to the
applicant*, and — the slice's substance — the two §3.2 persona doors: a customer becomes an agent
from inside their portal, and an agent takes up the customer hat and reaches the verification
wizard. Both must work **in the session the person is already in**.

### The live P0 this slice started from
**Every new signup was blocked by the consent re-acceptance modal.** `libs/auth/consent.ts`
hardcoded every consent version at `1.0.0` while the backend publishes `1.1.0` for Platform Terms
and Privacy, so an account was created having "accepted" versions that were already superseded and
met the non-dismissible re-acceptance modal on its first screen. `auth.spec.ts` never caught it
because it signs up, asserts a URL and stops — the modal opens over the page it asserted. The
registry no longer states versions: it names which consent *types* signup asks for, and
`ConsentStep` reads the published list through `authService.listConsentDocuments()`, recording the
version it actually displayed. That is what prevents a recurrence — there is no longer a second
place for a version to be written down. The `signup-consent-terms`/`-privacy` anchors are kept:
auth testids are contract.

### Defects it exposed, each fixed test-first
1. **A granted persona could not take effect until the next sign-in.** Claims were already read
   from the user record at each mint, but a refresh re-mints only the *access* token while the route
   guard decides from the **refresh** token — and nothing re-minted that. So applying granted AGENT
   and then bounced the applicant out of the agent area with no explanation, and an agent-path
   signup could never reach `/portal/*` at all. `SessionService.rotate_current_session` re-mints
   both and **moves the `device_sessions` row onto the new refresh hash** (the row is keyed by it;
   one left behind reads as revoked on the next refresh). Called by the new
   `POST /users/auth/personas/customer` and, best-effort, by the application submit.
2. **The client replayed a pre-grant routing verdict.** With the cookies correct, the browser still
   landed back on the portal. The trace showed *no request at all* for the agent dashboard: Next had
   prefetched the shell's links while the account still lacked the hat, the guard redirected every
   one of those prefetches, and `router.push` replayed the cached redirect. Fixed with
   `navigateAfterPersonaChange` — a full document load — used by both doors. **No unit test can see
   this**; it took a Playwright trace to find, which is the argument for the browser suite in one
   defect.
3. **The persisted session outlived the grant.** `useAuthStore` is `persist`ed to localStorage, so
   the reload rehydrated the pre-grant personas and `PortalSwitcher` never appeared. The grant
   endpoint's own response is a session and handles itself; the application submit answers with the
   application's status, so it now calls the new `useRefreshSession()` first.
4. **An existing customer could not become an agent at all** (found 2026-09-22): the persona was
   granted *by applying*, and applying *required* the persona. `proxy.ts` now exempts
   `/agents/apply` and only that route; `BecomeAnAgentLink` resolves the marketing CTA by session;
   a portal nav entry exists for someone who never revisits the marketing pages.
5. **The §3.1 gate had no exit for someone with somewhere to go.** The layout covered
   `/agents/apply` too, so a customer who followed the new link and changed their mind was held
   behind a layer that covers the nav. The gate is now scoped to the agent *area*; the application
   route renders its own wizard, whose close control appears only for someone holding CUSTOMER.
6. **Four unnamed/unbound controls**, all blocking axe: `CredentialsStep`'s licence, expiry,
   experience and bio inputs carried labels bound to nothing; `KycStep`'s ID-type Radix trigger and
   both DataTable `Select` triggers (the status filter and rows-per-page) were unnamed buttons.
   Bound with `useId()`, named with `aria-label` — the Slice 3/4 precedent.
7. **A rejected applicant was never told why.** `rejectionReason` rode on the status DTO and was
   rendered nowhere agent-facing, while the layout forced them back into a blank wizard — so the
   only move left was to resubmit the identical application and be refused again.
8. **`AsyncStateComponent` failed WCAG AA in its loading and empty states** (`text-gray-500`,
   4.39:1 on the app's surfaces; the error state used `text-red-500`). This is the component every
   surface renders while it waits, so the failure was everywhere and intermittent — the scan only
   catches it if it lands before the data does.
9. **Every admin table's horizontal scroll was keyboard-unreachable** (`overflow-x-auto` with no
   focusable ancestor). Only a phone engine exposes it, because only there do the tables overflow —
   the same lesson as Slice 4's findings block.
10. **A pending applicant's dashboard raised `ResourceNotFoundException` on every load**, because
    `useAgentProfileQuery()` was called unconditionally while its sibling was already gated on
    approval.
11. **Silent session recovery was dead — every refresh answered 500** (a regression inside this
    slice, from the refresh-reads-personas fix). Loading the user before minting moved
    `get_jwt_subject()` ahead of the `jwt_refresh_token_required()` that used to run inside
    `refresh_access_token`; `AuthJWT` has no subject until a token is verified, so it read `None`,
    looked up user `"None"` and raised `badly formed hexadecimal UUID string`. 17 refreshes, 17
    500s, and anyone whose access token lapsed was thrown to the login page. **Only
    `session.spec.ts` UAT-SESS-01 caught it** — the unit tests mocked `get_user_model`, so any
    subject passed. The controller now verifies first, and the refresh tests use a double that
    behaves like the library (no subject until verified), including one that pins the ordering.
    This is exactly why the plan re-runs `session.spec.ts` whenever refresh is touched.

### Misjudgements of mine, recorded so they are not repeated
- **I decoded the wrong cookie and nearly blamed the backend.** Checking whether the rotated token
  carried both personas, I read curl's jar after a request I had given `-b` but not `-c` — so I was
  reading the *login-time* token and concluded the grant had not reached the mint. The backend was
  correct all along. Decode the response's `Set-Cookie`, not the jar you sent.
- **I got `expectBothHats` backwards in both scenarios**, passing "the hat they just took up" when
  the switcher offers the hat they are *not* currently viewing. The helper now reads the direction
  off the URL, exactly as `PortalSwitcher` does, so the mistake is not available to make.
- **I asserted the portal switcher while a full-screen wizard covered it.** The trigger still reads
  as visible under a page-layer overlay; the click simply goes to the overlay.

### Folded in
- `POST /users/auth/personas/customer` — grants CUSTOMER and *only* CUSTOMER, so no client can
  claim a hat; `/agents/verify-property` is its UI, a route rather than a nav action so the grant
  completes before the navigation the guard would otherwise refuse.
- `NavItem.hiddenForCustomers` beside `hiddenForAgents`, applied by one shared `visibleNavItems`.
- `helpers/ui.ts:openNavItem` — layout-aware sidebar navigation, shared by both doors.
- `DATATABLE_TEST_IDS.SEARCH`, so the spec and the toolbar share one derivation.
- Anchors: `agent-apply-coverage/-experience/-bio/-rejection-reason`, `agent-verify-property*`.

### Verification
- **Gates:** backend ruff + mypy clean, unit **2273**; frontend Vitest **713** across 114 files,
  tsc + eslint clean.
- **Regression specs on chromium-desktop:** `auth.spec.ts` 13/13 and `session.spec.ts` 4/4, both
  first attempt, after the refresh fix. UAT-SESS-03 had a pre-existing check-then-read race on the
  recovery dialog (visible at the check, handed off to login before the read); it now reads the
  wording in the same step it finds the dialog.
- Two failures in the first matrix run were *my spec's* faults, not the product's: the admin search
  was typed before hydration (the repo's own documented trap — a half-written address matches
  nobody, which reads as a missing application), and the switcher assertion above.
- **A third spec fault, found by the chromium retry:** the open-drawer axe scan raced
  `DetailDrawer`'s framer-motion slide-in, a JS-driven animation the helper's `getAnimations()`
  wait cannot see, and read the sidebar through a half-faded backdrop (1.03:1). The drawer is
  `aria-modal`, so the scan is now scoped to it; the queue behind it is scanned uncovered first,
  in `openApplication`, so the table fixes above keep their coverage.

### Matrix result (`@P1`: chromium-desktop + webkit-mobile, single worker)
| engine | UAT-AGENT-01…05 |
|---|---|
| chromium-desktop | **5/5, first attempt** |
| webkit-mobile | **5/5, first attempt** |

**Final run: 10/10 on the first attempt, no retries** (7.2 min, single worker), after the refresh
fix and after UAT-AGENT-05 stopped asserting the "Verify a property" interstitial — on a fast stack
the grant lands before a check can see it, which is the right outcome; its wording is now pinned by
`VerifyPropertyContainer.test.tsx`.

**One earlier retry is explained, and it is not this slice's code.** Signup step 1's Continue button
was filled, enabled and visible, but never *stable* for 20s: it sits directly under the
password-strength meter, which animates in on a phone viewport and keeps pushing it. That is the
shared signup funnel (`helpers/signup.ts`, which `auth.spec.ts` drives identically), untouched
here; UAT-AGENT-01 passed first-attempt on webkit in the preceding run. Flagged for the auth
slice rather than widened now — a click that waits longer would hide the layout shift, not fix it.

**Environment, recorded so it is not misread later.** Two earlier multi-worker matrix runs
collapsed on this box: Docker Desktop's host↔Postgres path stalled under bursts of new connections
(`ConnectionResetError: [WinError 64]`, 356 in one run, requests reaching 144s), so OTP sends
timed out and every signup-based scenario failed while UAT-AGENT-04/05 still passed. Restarting
the Postgres container cleared it, and a single worker avoids the bursts. The machine also rebooted
mid-run once, which reads as 0 ms "failures" for everything after it — those tests never ran.

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

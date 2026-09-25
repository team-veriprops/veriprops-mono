# CLAUDE.md

@AGENTS.md

Next.js 16 (App Router) + React 19 + TypeScript. Tailwind v4, Radix UI primitives, Zustand, TanStack Query, React Hook Form + Zod.

## Commands

```bash
pnpm install
pnpm dev          # http://localhost:3000
pnpm build
pnpm start
pnpm lint
pnpm typecheck    # tsc --noEmit — a CI gate; neither `lint` nor `build` typechecks test files
pnpm test         # vitest run
pnpm test:watch
```

Single test:

```bash
pnpm vitest run path/to/file.test.ts
pnpm vitest run -t "test name pattern"
```

## API proxy

`/api/*` requests are rewritten to `${API_BASE_URL}/api/*` by [next.config.ts](next.config.ts). `API_BASE_URL` is server-only (read from [src/lib/config/server.ts](src/lib/config/server.ts), which throws if imported on the client). Public env vars (`NEXT_PUBLIC_*`) live in [src/lib/config/public.ts](src/lib/config/public.ts) — keep them split. The proxy target/timeout and dev origins are env-driven (`NEXT_PUBLIC_API_PREFIX`, `PROXY_TIMEOUT_MS`, `ADDITIONAL_DEV_ORIGINS`).

## Env files

Committed, **config-only** env files, in two groups. **Minimal-diff rule:** [.env](.env) is the base + catalog (documents every settable key); every other file declares only keys whose value genuinely differs from `.env` for that environment (or pins a policy against `.env` drift, e.g. the prod OAuth toggles) — never replicate a key just to repeat the same value.

- **Next.js-native (auto-loaded):** [.env](.env) (shared base = local-dev values, documents every settable key), [.env.test](.env.test) (deterministic automation env, auto-loaded under `NODE_ENV=test`; Next.js deliberately skips `.env.local` in test mode), and [.env.production](.env.production) (prod-shaped build defaults for every `next build`). `.env.local` stays git-ignored for personal overrides + `BACKEND_SECRET_KEY`.
- **Deploy-time (NOT loaded by Next.js):** [.env.dev](.env.dev) and [.env.staging](.env.staging) are the config **base** for the deployed dev/staging previews (`NODE_ENV` has no dev/staging value, so Next.js can't load them). `deploy.yml` merges the selected file with the matching Doppler config via `.github/scripts/doppler_env_args.sh` (Doppler wins per key) and passes the merged set to `vercel deploy` as `--build-env`/`--env` flags, which override `.env.production` during the build. Consequences: file values must contain no spaces, only keys meant to override `.env.production` belong there, and **never a secret key** — a committed value would shadow the Doppler entry in review even though Doppler wins at deploy.

Secrets are Doppler-managed (project `veriprops-verf-frontend`, configs `prd`/`stg`/`dev`) and are injected by `deploy.yml` itself: the environment-scoped `DOPPLER_TOKEN_FRONTEND` service token selects the config, and every key ships as deployment-scoped `--build-env`/`--env` flags for dev, staging **and** production (production's file base is `.env.production`, auto-loaded by `next build`). There is **no Doppler→Vercel sync and no dashboard env vars** — staging and dev can hold different secret values, rollbacks restore the env a deployment shipped with, and a rotated Doppler value takes effect on the next deploy. The only live frontend secret (`EDGE_AUTH_SECRET`) is a single zone-wide value shared with the backend and the Cloudflare Transform Rule. Never store a *blank* secret value in a Doppler config — it overrides the file placeholder and (for `EDGE_AUTH_SECRET`) silently disables the trusted-edge check. **Never put a secret in a `NEXT_PUBLIC_*` var** (build-time inlined into the bundle). The backend hygiene guard (`backend/test/unit/app/config/test_env_hygiene.py`) scans all five committed files and fails on any credential-shaped value. Runtime flags still come from the backend's `/config/public`, not new env vars.

## Client operational constants

Non-env client tuning that would otherwise be duplicated as magic numbers lives in one module: [src/lib/config/app.ts](src/lib/config/app.ts) — pagination defaults (`DEFAULT_PAGE_SIZE`, `DEFAULT_HISTORY_PAGE_SIZE`, `CHAT_MESSAGES_PAGE_SIZE`), SSE reconnect (`SSE_MAX_RETRIES`/`SSE_BASE_BACKOFF_MS`), TanStack Query cadence (`REFETCH_INTERVAL_MS`/`STALE_TIME_MS`/…), `DEFAULT_DIAL_CODE`, upload caps, and `SUPPORT_EMAIL`. Import from here rather than re-hardcoding a page size / interval. **Backend-owned limits are not duplicated here** — e.g. the chat composer `maxLength` reads `chatMessageMaxLength` from `/config/public` (`usePublicConfigQuery`), with `app.ts` holding only a pre-resolve fallback.

## Auth Guard

- Use Next.js `proxy.ts` to control access to protected routes.

  * Centralize route protection in `proxy.ts` rather than duplicating auth checks across pages or layouts.
  * Validate authentication state (session, token, or cookie) in `proxy.ts` before allowing access to protected routes.
  * Redirect unauthenticated users to the sign-in page.
  * Redirect authenticated users away from guest-only routes (for example: sign-in, sign-up) when appropriate.
  * Keep route matching explicit and maintainable by clearly defining protected, public, and guest-only route groups.
  * `proxy.ts` should handle **access control only**; page-level authorization and business rules should remain in the application layer.

### Security invariants (do not regress)

- **Trusted-edge check.** `proxy.ts` runs `isEdgeAuthorized` ([lib/edgeAuth.ts](src/lib/edgeAuth.ts)) first, on a match-everything matcher (except Next internals/static): when the server-only `EDGE_AUTH_SECRET` env var is set, requests lacking the Cloudflare-injected `x-edge-auth` header get 403 — closing the `*.vercel.app` bypass around the Cloudflare WAF. Unset/blank/`CHANGE_ME` ⇒ open (local/test/e2e). Never expose the secret as `NEXT_PUBLIC_*`; keep header name/semantics in sync with the backend `EdgeAuthMiddleware`. Don't re-narrow the matcher to protected routes only.
- **Open-redirect guard.** Any post-auth navigation to a user-supplied `?redirect=`/`next` value must pass through `isSafeRedirectPath` / `resolvePostAuthRedirect` ([components/website/auth/libs/auth/redirect.ts](src/components/website/auth/libs/auth/redirect.ts)) — a bare `startsWith("/")` is insufficient (`//evil.com` and `/\evil.com` are cross-origin). Only same-origin relative paths are accepted.
- **JSON-LD escaping.** `<JsonLd>` escapes `<`/`>`/`&` before `dangerouslySetInnerHTML` so a string value can't break out of the `<script>` tag. Don't bypass it.
- **Automation hooks are fail-closed.** `isAutomationEnvironment()` ([lib/automation.ts](src/lib/automation.ts)) is an allowlist (`dev_personal`/`development`/`test`); staging/production/unset all return `false`. Never invert it or add prod-enabling values.
- **No leaking backend errors to the console.** `FetchHttpClient` must not `console.log` response bodies (they may carry PII/internal detail).
- **A 403 navigates the whole page to `/forbidden`.** `FetchHttpClient` treats it as "this session lacks permission" and hard-redirects. That is right for the authenticated app and wrong for a public page whose *expected* failure is a dead link, so those endpoints answer **not-found** instead (the WhatsApp handoff landings do; so does a revoked share token). If you add a public capability-link surface, don't return 403 for a spent link — you will replace your own recovery page with the access-denied screen.

## Session recovery (token refresh UX)

`FetchHttpClient` auto-refreshes the session (401-triggered and proactively via `useProactiveSessionRefresh`, mounted in `ClientWrapperProvider`, ~60s before `accessTokenExpiresAt`). The refresh has a **transient-only retry budget**: network/5xx failures retry up to `SESSION_REFRESH_MAX_ATTEMPTS` with doubling backoff; a definitive rejection (401/403/419 from the refresh endpoint) short-circuits. The plain-TS client talks to React through the vanilla Zustand bridge [src/lib/sessionRecovery.ts](src/lib/sessionRecovery.ts) (`idle`/`reconnecting`/`expired` — attempt 1 stays silent so routine refreshes never flash UI), rendered by the globally-mounted [SessionRecoveryOverlay](src/components/website/auth/SessionRecoveryOverlay.tsx) (testids `session-recovery-overlay`/`session-recovery-attempt`/`session-signin-now`). On `expired` the overlay clears `useAuthStore` and hands off to `loginRedirectUrl(...)` (loop-guarded on `/auth*`) after a brief pause. The refresh endpoint returns the full `AuthSession` DTO; the overlay pipes it into `useAuthStore` so expiry timestamps stay fresh — `src/lib` must never import components, so that wiring lives on the React side. Tuning constants live in [src/lib/config/app.ts](src/lib/config/app.ts); the client is unit-tested in [FetchHttpClient.test.ts](src/lib/FetchHttpClient.test.ts) and the HTTP contract is pinned by the backend e2e stage `session_refresh`.

### Taking up a persona (§3.2) — three client copies go stale at once

Personas are additive and granted from inside the product: a customer applies to become an agent (`/agents/apply`), an agent takes up the customer hat (`/agents/verify-property` → `useGrantCustomerPersonaMutation`). The backend rotates the session so the new hat works immediately (see the backend's rotation note). **The client is the hard part** — three separate copies of "who this browser belongs to" survive the grant, and all three must be dealt with or the account holds a hat the app refuses to admit to:

1. **The router cache.** The whole time the wizard was on screen, Next prefetched the shell's links — and the guard answered every prefetch of the area they could not yet enter with a redirect, which the client cached. A `router.push` there afterwards replays that cached verdict *without asking the guard again*: no request is made, and the user lands back where they started. So navigate with `navigateAfterPersonaChange` ([lib/session-navigation.ts](src/lib/session-navigation.ts)), a full document load, never `router.push`/`replace`. This is invisible in any unit test and reproduces only in a browser.
2. **The persisted auth store.** `useAuthStore` is `persist`ed to localStorage, so the reload rehydrates the *pre-grant* session and `PortalSwitcher`, the sidebar's `hiddenForAgents`/`hiddenForCustomers` filtering and `dashboardFor` all keep deciding from it. A grant whose response is not itself a session — submitting an application answers with the application's status — must call `useRefreshSession()` before navigating.
3. **The cookies**, which the backend has already rotated; nothing to do, but they are why a hard navigation is enough.

The pair UAT-AGENT-04/05 in `agent-onboarding.spec.ts` exists to catch all three: each direction is taken up from inside the product and must end with both hats switchable, in the same session.

## Route Definition
* All routes in the application should be declared in `frontend\src\lib\routes.ts` grouped by their surface.
* All Portal Menu Sidebars are grouped and maintained here `frontend\src\components\portal\nav.ts`,
Admin here `frontend\src\components\admin\nav.ts` and Agents here `frontend\src\components\agents\nav.ts`.
* **Compulsorily**: Make sure all routes in the app is declared and that various Menu sidebars are up to date.

## Tables (DataTable)

The shared table lives at [src/components/ui/table/DataTable.tsx](src/components/ui/table/DataTable.tsx). It is **controlled and presentational** — it fetches nothing and holds no query state.

- The parent owns `{ page, query, orderBy, ...filters }` via `useSyncedQueryState` ([src/hooks/useSyncedQueryState.ts](src/hooks/useSyncedQueryState.ts)) so the state is URL-synced, and passes `searchValue`, `orderBy`, `filters`, and `updateFilters`. `updateFilters` must forward **all** keys it receives (not just `page`) to the query hook — search/sort/filter/pagination are emitted through that one callback.
- Filters render **inside** the toolbar via the `filters` prop (a `TableFilter[]` — `{ key, label, value, options }`). Don't build a separate external filter bar.
- Search, filtering, and pagination are **server-side**. The backend list endpoint accepts `page`/`page_size`/`query` (see the root [CLAUDE.md](../CLAUDE.md) pagination convention); the frontend service just forwards them. Do not filter client-side.
- **Suspense rule (Next 16):** any `page.tsx` that renders a DataTable — or anything else reading `useSearchParams`/`useSyncedQueryState` — must wrap its client component in `<Suspense>`, or the page throws "missing-suspense-with-csr-bailout" on hard navigation.
- Representative consumers: [src/components/admin/team/AdminTeamManagement.tsx](src/components/admin/team/AdminTeamManagement.tsx), [src/components/admin/verifications/AdminVerificationList.tsx](src/components/admin/verifications/AdminVerificationList.tsx), [src/components/admin/agents/AgentApplicationsAdmin.tsx](src/components/admin/agents/AgentApplicationsAdmin.tsx).

## Drawers

Record-detail views and one-off forms / centered modals use the shared right-side slide-over [src/components/ui/DetailDrawer.tsx](src/components/ui/DetailDrawer.tsx) (`side?: "right" | "left"`, default right; size via `DetailDrawerWidth`). Don't hand-roll `fixed inset-0` modals.

- Deep-linkable detail **routes** wrap their content in [src/components/ui/DrawerRoutePage.tsx](src/components/ui/DrawerRoutePage.tsx) — open on mount, close → `router.back()` (with a fallback href) — so the URL stays deep-linkable and refresh-safe while presenting as a drawer.
- Multi-step `WizardOverlay` flows (agent apply, portal submission/pay) stay **full-screen** — do not convert them to drawers.

## Real-time, Chat & Notifications (top nav)

- **One SSE transport.** Server→client pushes ride Server-Sent Events (§4.9); sends are ordinary HTTP POST. Two hooks: [src/lib/useVerificationStream.ts](src/lib/useVerificationStream.ts) (verification-scoped, `/api/verifications/{id}/stream`) and [src/lib/useUserStream.ts](src/lib/useUserStream.ts) (per-user, `/api/chat/stream` — carries `chat_message`/`chat_unread`/`notification`/`notification_unread`). SSE only *invalidates* queries; a 60-second `refetchInterval` poll is the durable fallback, so a dropped push never leaves the UI stale.
- **Top-nav order is fixed: Support → Chat → Notifications → Account** (`AppShell`). `ChatButton` ([src/components/chat/ChatButton.tsx](src/components/chat/ChatButton.tsx)) and the real `NotificationBell` ([src/components/shared/notifications/NotificationBell.tsx](src/components/shared/notifications/NotificationBell.tsx)) each mount the per-user SSE subscription (`useChatRealtime`/`useNotificationRealtime`) so their counters stay live app-wide. Counters are numeric, cap at "9+", and hide at zero.
- **Backend owns chat + notification copy, routing, counters, and the fraud-hold state** — the frontend renders what it receives. Chat threads reuse the shared [src/components/chat/ChatThread.tsx](src/components/chat/ChatThread.tsx); a held message shows its backend-supplied `heldNotice`. Services mirror the backend contracts: `chat-service` / `notification-service` under `components/{chat,notifications}/libs/`.

## SEO (every public page)

- Build a page's metadata with `buildMetadata({ title, description, path, image?, type?, noindex? })` from [src/lib/seo.ts](src/lib/seo.ts) — export it as `metadata` (static) or `generateMetadata` (dynamic). It sets canonical, Open Graph, Twitter, and robots from one place; don't hand-roll `Metadata`.
- Add structured data with `<JsonLd data={...} />` ([src/components/seo/JsonLd.tsx](src/components/seo/JsonLd.tsx)) using the builders in `seo.ts` (`organizationJsonLd`, `websiteJsonLd`, `faqJsonLd`, `legalDocumentJsonLd`, `pricingJsonLd`). Pricing structured data is a schema.org `Service` with one `Offer` per tier, built from the same backend prices the page renders (`withLivePrices` in `home.data.ts`), and omitted entirely when no tier is priced.
- **UI decisions are SEO decisions.** Judge assets and rendering by what a crawler receives and by Core Web Vitals:
  - Indexable content that the backend owns (prices) is rendered in the server HTML.
  - Fonts are self-hosted through [src/lib/fonts.ts](src/lib/fonts.ts) (`next/font`), never a runtime `@import` from a third-party origin. A guard test in `src/styles/` enforces this.
  - Images are local files served through `next/image` with accurate `sizes`.
  - The above-the-fold LCP image is preloaded. An image hidden at a breakpoint gets a `1px` `sizes` entry for that breakpoint, so the browser only fetches a tiny candidate there.
- Keep [src/app/sitemap.ts](src/app/sitemap.ts) and [src/app/robots.ts](src/app/robots.ts) current: public marketing + legal routes are crawlable; `/portal`, `/admin`, `/agents`, `/account`, `/auth` are disallowed. VID-lookup pages pass `noindex` until `COMPLETED`.

## WhatsApp channel surfaces (PRD §26)

- **The widget** ([components/website/WhatsAppWidget.tsx](src/components/website/WhatsAppWidget.tsx)) mounts once in `ClientWrapperProvider`, so it rides every surface without per-layout wiring. It is `position: fixed` — that is what makes "zero CLS" structural rather than a promise — and it renders **nothing** until `/config/public` supplies the number: the number is the customer's anti-impersonation anchor (§26.1.2), so there is deliberately no hardcoded fallback. It suppresses itself inside the payment flow (§26.4.1).
- **Page codes** ([lib/whatsapp.ts](src/lib/whatsapp.ts)) are the one thing here the backend does not own — they describe frontend routes it does not model. Explicit entries win; anything else derives from the first path segment, so a new page stays attributable without a table edit (§26.10). Payment-flow suppression matches `PAYMENT_FLOW_PATH_PATTERNS` in [routes.ts](src/lib/routes.ts), kept beside the route builders it mirrors.
- **Handoff landings** (`/wa/{pay,upload,report}/[token]`, [components/website/handoff/](src/components/website/handoff/)) are public by design — the token is the authorization, so they must stay out of `PROTECTED_PREFIXES`. Redemption happens in an **effect, never during render**: it is single-use, and WhatsApp fetches the URL to build its link preview. The page must acknowledge the case it picked up (silent context loss is a spec violation) and must **never** explain why a link failed — expired, spent, and forged are one state. Only `pay` completes there; `upload`/`report` hand into the authenticated portal (D50).
- **Source labels.** WhatsApp and the website feed one admin console, so a thread/message carries `channel`/`source` and renders [ChannelBadge](src/components/chat/ChannelBadge.tsx). Web is the unlabelled default, so the badge means "notice this" rather than decorating every row. Three per-message markers ride the same principle, each rendered only when its field is set: `unofficialMedia` ("not evidence" — §26.1.6's rule, on every chat-borne image, document or voice note), `mediaKind` (an audio marker for a voice note), and `pendingChannelDelivery` (an agent reply that is in the thread but has not left over WhatsApp yet, because it was typed outside Meta's 24-hour window). The last one matters most: without it an agent believes their message sent. All three are backend-derived — never recompute them client-side — and `mediaKind` renders through `humanizeEnumLabel`, never as a raw enum string. Two more follow the same rule (D92): `channelStatus` renders `DeliveryTicks`, an icon plus words, so colour is never the only signal. The backend sends it only to admin viewers. `seenBySupport` renders "Seen" on the viewer's own messages only. Playwright drives receipts with `wa.status(wamid, status)`.
- **The §26.7 template registry** lives at `/admin/config/whatsapp-templates` ([WhatsAppTemplates](src/components/admin/config/WhatsAppTemplates.tsx), `CONFIGURE_SYSTEM`) and is **read-plus-sync, never editable**: the definitions are code-owned on the backend and the status is Meta's, so an input here would let the page claim something the app does not do. `NOT_FOUND` is ours rather than Meta's — declared but never submitted — and is the state the §26.11 launch gate actually asks about, so it renders as needing attention, not as a failure.
- **Account linking** (§26.4.4) lives at `/account/whatsapp` ([WhatsAppLinkSettings](src/components/account/WhatsAppLinkSettings.tsx)) — its own page rather than a section of `/account/linked`, which is OAuth-provider specific. Only `WhatsAppLinkStatus.ACTIVE` means linked: a `PENDING` row carries a number but grants nothing, so never infer "linked" from a number being present. `/wa/link/[token]` is the one `/wa/*` landing inside `PROTECTED_PREFIXES` (`WA_LINK_PREFIX` in [routes.ts](src/lib/routes.ts)) — the token says which number is being claimed, the session says which account claims it. That page **must never send a number**: it posts the token alone, so a signed-in attacker cannot have a code delivered to a number the bot never messaged.
- **A customer's WhatsApp thread opens at `/portal/chat/[conversationId]`** ([CustomerConversationContainer](src/components/chat/CustomerConversationContainer.tsx), D90). It is also `GENERAL_SUPPORT`, so where a thread opens is decided in one place — `conversationHref` in [libs/conversationLinks.ts](src/components/chat/libs/conversationLinks.ts), shared with the list's title/subtitle helpers — and checks the channel first. The thread's `readOnly`/`readOnlyReason` are backend-derived from the membership's visibility window; `ChatThread` takes the words to show as `readOnlyNotice` (the reason→copy map lives beside `conversationHref`), and a refused send is a 400, never a 403.
- **The admin messaging console is one page, two tabs** (`/admin/messages` → [AdminMessagesTabs](src/components/chat/AdminMessagesTabs.tsx)): the §11.2 hold-review queue and the Conversations inbox ([AdminConversationsInboxContainer](src/components/chat/AdminConversationsInboxContainer.tsx)). Decision K puts every surface in one console, so don't split them across routes. The active tab is `?tab=` ([adminMessagesTab.ts](src/components/chat/libs/adminMessagesTab.ts)), which is how an admin's `ChatButton` opens the inbox. The inbox is **server-driven** (§16.5, D91): `useAdminConversationsQuery` pages `GET /admin/conversations` with the backend's `AdminInboxFilter` facet and a search. It covers cases, web support and WhatsApp, and never filters the member `/chat/conversations` list client-side. Its query key nests under `chatKeys.conversations()`, so every existing invalidation (SSE, read, send) refreshes it. Rows are named by `adminConversationTitle`/`adminConversationSubtitle` (backend `ownerName`/`ownerEmail` for support threads). Replies post through `useConversationSendMutation` (by conversation id), because a support or WhatsApp thread has no verification to send by. A server-paged list that is not a DataTable pages with [ListPager](src/components/ui/ListPager.tsx).
- **[AssistantModeBanner](src/components/chat/AssistantModeBanner.tsx) is not decoration.** A thread goes sticky-`HUMAN` the moment an agent replies (D57, generalized in D93 to every assistant-enabled thread — web support and per-case customer↔admin threads, not just WhatsApp) and stays there until it is handed back — and that state is **invisible from the message list**, where a silenced assistant looks exactly like a working one. The banner is keyed by `conversationId` (not phone) and is the only way a person can see the state or undo it, so any admin surface that can reply must render it — it is mounted unconditionally on both [AdminConversationsInboxContainer](src/components/chat/AdminConversationsInboxContainer.tsx) and [AdminMessagesContainer](src/components/chat/AdminMessagesContainer.tsx)'s Customer tab (it self-hides via the `enabled` flag when the thread has no assistant surface, e.g. an Agents-tab thread). It is admin-only (`MANAGE_VERIFICATIONS` for the session read/hand-back — the same permission that lets an admin reply, so the banner never 403s an admin into `/forbidden`), so never mount it on a customer surface. It carries a second invisible state, WhatsApp-only: `windowOpen` says whether Meta's 24-hour service window is still open, which an agent needs **before** typing — outside it their words are queued behind a `window_reopen` nudge rather than delivered; a web thread has no window and the banner skips the chip. Both facts come from the one `GET /admin/assistant/sessions/{conversationId}` call ([assistant-service.ts](src/components/chat/libs/assistant-service.ts) / `useAssistantSessionQuery`) the banner already makes, so showing them costs no extra request.
- **`/wa/intake/[token]`** ([WaIntakeLanding](src/components/website/handoff/WaIntakeLanding.tsx)) is the second `/wa/*` landing inside `PROTECTED_PREFIXES` (`WA_INTAKE_PREFIX`), for the same reason as linking: the token carries a *conversation*, the session says whose draft its answers become (D69). It redeems in an **effect, never during render** (single-use, and WhatsApp fetches the URL for its preview card), then `router.replace`s into the existing submission wizard — the seeded draft is what the wizard resumes, so there is no chat-specific consent or payment surface to keep in sync. A dead link gets the same one indistinguishable state as every other handoff landing.
- **[WhatsAppContinueButton](src/components/portal/WhatsAppContinueButton.tsx)** is the web→chat half of continuation (§26.4.3, D58). `waContinueUrl` pre-fills the `VP-…` reference, which the bot matches on the customer's literal words — without it the customer must go and find a reference before the chat can help. Like the widget, it renders **nothing** without a configured number: no hardcoded fallback, ever (§26.1.2).
- **The two §26.4.6 opt-ins are one shared control on two payment surfaces** ([WhatsAppOptInControls](src/components/shared/whatsapp/WhatsAppOptInControls.tsx), D76). It renders on the authenticated pay screen ([PayContainer](src/components/portal/submission/PayContainer.tsx)) **and** on the `/wa/pay/[token]` landing, because the customer who arrived from chat is asked there or nowhere — and §26.10 counts the opt-in rate as the channel's consent asset. It lives in `shared/` for exactly that reason: the two surfaces write through different endpoints (one session-authenticated, one grant-scoped), so only the markup and the words are shared, and the two cannot drift into asking different questions. Three properties are requirements, not styling: they are **two** controls (bundling would leave the marketing consent unevidenced), they render **unticked** from the backend's "no record" state (a pre-ticked box is not consent), and they are written **on toggle** rather than on payment success — the tick is the consent act, and a failed card must not discard it. Revocation lives on `/account/whatsapp` ([WhatsAppConsentSettings](src/components/account/WhatsAppConsentSettings.tsx)), which is the **only** place marketing consent can be given back: a chat `START` restores progress updates alone (D64).
- **[DelegatePanel](src/components/portal/verifications/DelegatePanel.tsx) sits between "Your agents" and "Evidence" on the case page**, and that position is the grant rendered: with the people on the case, ahead of the material a §26.4.5 delegate must never see. Its copy states the limits before the buyer uses it — one person, status updates only, never documents or the report — because a buyer who believes they are sharing the report is surprised twice, once here and once when their delegate asks why they cannot open it. The awaiting-code state is rendered plainly rather than as a spinner: it lasts as long as it takes the buyer to reach the person and read the code back, and hiding it makes them nominate again because nothing appeared to happen. Confirmation posts the **code alone** — which number is being confirmed comes from the authorization already on the case, so a browser can never redirect a code to a number nobody nominated.
- **Channel analytics is a tab on `/admin/analytics`, not a route** ([WhatsAppChannelAnalytics](src/components/admin/analytics/WhatsAppChannelAnalytics.tsx), D86). Same reasoning as `AdminMessagesTabs`: the platform funnel and the channel funnel are the same question asked of two surfaces, and separate routes would make the channel look like a separate product. It reuses [StatCard](src/components/ui/StatCard.tsx) and [MiniBarBreakdown](src/components/ui/MiniBarBreakdown.tsx) — the **no external charting dependency** rule stated at the top of `AdminAnalytics.tsx` holds for this tab too; `recharts` is in `package.json` but only the untouched shadcn wrapper imports it. Three things here are requirements rather than layout: every **rate renders the counts behind it** (60% over three conversations and over three hundred call for opposite decisions, and a percentage alone cannot tell them apart); the **Meta quality rating renders its sync age** (a GREEN nobody could refresh for a week is a different fact from this morning's, and `syncError` is what distinguishes them); and a **never-synced rating is never toned as healthy** — §26.11 treats it as a launch gate, so the absence of Meta's verdict must not read as a clean bill of health. Page codes keep their hyphens through `humanizeEnumLabel`, deliberately: they are identifiers to match against [lib/whatsapp.ts](src/lib/whatsapp.ts), not status labels.

## Backend-served content & public flags

- Legal pages render content the backend owns: the dynamic `/legal/[slug]` route fetches via [src/lib/legal.server.ts](src/lib/legal.server.ts) (`fetchLegalDocument`/`fetchLegalDocuments` → `/api/users/auth/consents/documents/...`) and renders Markdown through `LegalDocument`. Do not hardcode legal prose on the frontend.
- Server-rendered pages read the backend through [src/lib/backend-fetch.server.ts](src/lib/backend-fetch.server.ts) (`fetchBackendData(path, caching)` → envelope `data` or null), which `legal.server.ts`, `public-lookup.server.ts` and `public-config.server.ts` share — don't add another fetch-and-unwrap. Backend-owned figures a public page shows (tier prices) are fetched in the server page and passed down as props, never hardcoded as a client fallback: a client-only query renders different HTML on the server and in the browser, which is a hydration mismatch. `fetchPublicConfig()` returns null when the backend is unreachable so `next build` can prerender without one.
- Read runtime flags from the backend, not from `NEXT_PUBLIC_*`. `usePublicConfigQuery()` exposes `/config/public` (e.g. `phoneVerificationEnabled`, which drives whether the signup flow shows the phone-verification step).
- The `/account/*` security surface (security log, devices, linked accounts, password) lives under `src/app/account/` on `AppShell`; the `PortalSwitcher` in the shell shows the cross-portal badge for multi-persona users.

## Styling

All styling is `className` (Tailwind v4 utilities, generated from [src/styles/theme.css](src/styles/theme.css)'s CSS-first `@theme inline` config) — never the `style` prop. Conditional styling uses `cn()` from [src/lib/utils.ts](src/lib/utils.ts) to merge a base class string with per-branch classes, never a `style={condition ? {...} : {...}}` object. Inline `style` is reserved for two narrow, permanent exceptions:

- **Runtime-computed numeric values** that can't be expressed as a static class: bar-fill/column widths derived from data ratios ([MiniBarBreakdown.tsx](src/components/ui/MiniBarBreakdown.tsx), [AdminAnalytics.tsx](src/components/admin/analytics/AdminAnalytics.tsx)), the sidebar slide transform in [AppShell.tsx](src/components/ui/AppShell.tsx), and per-column pixel widths in [DataTable.tsx](src/components/ui/table/DataTable.tsx).
- **Vendored third-party CSS-variable contracts** in `src/components/3rdparty/ui/` — `sidebar.tsx`, `sonner.tsx`, and `chart.tsx` theme Radix/Sonner/Recharts by injecting CSS custom properties via `style={{ "--foo": value } as React.CSSProperties}`, which is the documented way to theme those libraries; `progress.tsx`'s Radix fill uses `style={{ transform: ... }}`, the standard Radix animation pattern.

A colour class naming a token the theme doesn't define (`bg-brand`, `text-brand-primary`) is **not** a build error in Tailwind v4 — it silently generates no CSS, which is how the 404 page shipped a white label on a transparent button. Use only the `--color-*` tokens declared in `theme.css`; [styles/theme-tokens.test.ts](src/styles/theme-tokens.test.ts) fails on any `*-brand-*` utility without one. Full-page dead ends (404, 403) render through [StatusPage](src/components/ui/StatusPage.tsx); send a user "back to their dashboard" with `dashboardFor(user)` ([redirect.ts](src/components/website/auth/libs/auth/redirect.ts)), never a hardcoded surface. `proxy.ts` uses the same function with `{ fallback: ROUTES.HOME }` — keep that fallback: a signed-in session with no persona sent to `/portal` would be bounced by the portal guard straight back, an infinite redirect.

Nothing else should use `style`. If a color/shadow/gradient value isn't yet exposed as a theme token, prefer a Tailwind arbitrary-value class (`bg-[...]`, `shadow-[...]`) over inline `style` — it keeps the value in `className` even before it earns a real token.

## Design system (shared UI primitives)

Reach for the shared primitive before hand-rolling markup — the card/tile visual language is centralized so every surface stays consistent.

- **Card-style choosers** use [src/components/ui/SelectableCard.tsx](src/components/ui/SelectableCard.tsx): an icon tile + title/description with a primary selection ring. Pass `selectionMode="radio"` (single-select) or `"checkbox"` (multi-select) — it sets the ARIA role + `aria-checked` and shows a check badge when a checkbox is selected. Optional `badge` (inline pill by the title) and `footer` (block below, e.g. a licence-required pill) slots. Consumers: submission property-type ([PropertyStep](src/components/portal/submission/PropertyStep.tsx)), agent role + KYC-method ([RolesStep](src/components/agents/onboarding/RolesStep.tsx), [KycStep](src/components/agents/onboarding/KycStep.tsx)). Do **not** re-roll the `rounded-xl border … ring-1 ring-primary` markup inline.
- **Stat tiles** use [src/components/ui/StatCard.tsx](src/components/ui/StatCard.tsx) (label + value, optional `href`/`icon`/`tone`/`hint`). **A linked card must show its link affordance:** when `href` is set, `StatCard` auto-renders an `ArrowUpRight` indicator (top-right) and moves the metric icon inline — never rely on a hover border alone to signal a card is clickable. `AttentionChip` and `LinkCardRow` carry the same affordance.
- **Status chips** use [src/components/ui/StatusPill.tsx](src/components/ui/StatusPill.tsx): a tone-coded, humanized pill. The exported `statusTone(status)` resolves any backend status/state enum value → tone (`positive`/`warning`/`negative`/`active`/`muted`); extend its map rather than re-rolling colored spans. Consumers: finance/payouts, disputes, erasure, task console.
- **Status distributions** use [src/components/ui/MiniBarBreakdown.tsx](src/components/ui/MiniBarBreakdown.tsx) — dependency-free CSS bars over a `Record<status, count>` (e.g. `FinanceSummary.paymentsByStatus`), labelled with `StatusPill`.
- **Operational signals** use [src/components/ui/AttentionChip.tsx](src/components/ui/AttentionChip.tsx) — a "needs attention" chip (icon + `tone` + optional `href`) for backend-derived counts / SLA breaches.
- **Recent-item rows** use [src/components/ui/LinkCardRow.tsx](src/components/ui/LinkCardRow.tsx) (title + subtitle + trailing slot + chevron) — shared by the admin/portal dashboards.
- **Page scaffold.** [src/components/ui/PageShell.tsx](src/components/ui/PageShell.tsx) wraps a page's content in the standard centered container + [PageHeader](src/components/ui/PageHeader.tsx) (with optional `actions`/`meta` slots). It's an **inner content wrapper only** — it does not touch `AppShell`/nav. Dashboards and admin finance/compliance surfaces use it; when a `page.tsx` adopts `PageShell`, drop any padding wrapper in the route file so it isn't double-applied (keep `<Suspense>`).
- **Rendering enum values.** Never print a raw enum/DB string (`GOV_ID`, `UNDER_REVIEW`, `FIELD`) in the UI. Route it through `humanizeEnumLabel` from [src/lib/utils.ts](src/lib/utils.ts) (→ "Under Review"), or a small explicit label map when the humanized form is wrong (e.g. `BVN`). This also covers enum values inside `.map()` object literals (chart/filter labels), not just direct JSX. Compare on the enum, display via `humanizeEnumLabel`.
- **Full-screen wizards** (submission, agent apply) share [src/components/ui/wizard/WizardOverlay.tsx](src/components/ui/wizard/WizardOverlay.tsx) — a stepper + footer shell; keep step content in per-step components and thread a `testIdPrefix`. Pass `closable={false}` to hide the close control for a compulsory flow the user cannot dismiss (e.g. the agent-onboarding gate below) — default is closable. The overlay sits on the shared page layer (see **Layering** below).
- **Layering.** A full-screen page layer (wizard, report access gate) takes `PAGE_OVERLAY_LAYER` from [src/components/ui/layers.ts](src/components/ui/layers.ts), which documents the whole order: chrome `z-40` < page layers `z-45` < Radix portals + `DetailDrawer` `z-50` < toasts. Never hand-roll a `fixed` layer above `z-50`. A global mandatory modal (`ConsentReacceptanceModal`, `SessionRecoveryOverlay`) can open over any page, and Radix disables pointer events outside an open modal, so a page layer painted on top leaves the user a visible screen they cannot use. A Select/Popover opened inside such a layer would render invisibly behind it too. [layers.test.tsx](src/components/ui/layers.test.tsx) pins the order and fails on any app-owned `fixed` layer above `z-50`.
- **Pay-step phone gate** (PRD §10.5) is [PayPhoneGate](src/components/portal/submission/PayPhoneGate.tsx), rendered by `PayContainer` while `session.user.phoneVerified` is false — the one surface where a customer confirms or corrects their number and OTP-verifies it before their first payment. It sends the number with both calls so the backend verifies exactly the number the code went to; the backend owns uniqueness and saves the number only once verified. The `/wa/pay/[token]` landing has no session, so when redemption says `phoneVerificationRequired` it links into the portal pay page rather than duplicating this gate.
- **Non-dismissible dialogs.** [src/components/3rdparty/ui/dialog.tsx](src/components/3rdparty/ui/dialog.tsx)'s `DialogContent` takes `preventOutsideClose` — blocks Escape and outside-click dismissal (Radix's default `showCloseButton={false}` alone only hides the ✕ button, it doesn't stop those). Use both together for a truly mandatory modal (e.g. `ProfileCompletionModal`).

## Layout

- `src/app/` — App Router. Top-level segments are isolated user surfaces:
  - `(website)/` — public marketing + auth (login, signup, OAuth, password flows) + account.
  - `portal/` — authenticated user area.
  - `admin/` — internal admin.
  - `agents/` — agent-facing area.
- `src/components/{surface}/` — components grouped by the surface they serve (`website/`, `portal/`, `admin/`, `agents/`, `account/`, `nav/`, plus shared `ui/` and `3rdparty/`). Keep components close to the surface that owns them; promote into `ui/` only when reused by 2+ surfaces.
- `src/components/ui/` — primitives + Radix wrappers (`AsyncStateComponent`, `table`, form helpers `form/`, `verified_input/`, `BrandLogo`, `CopyText`, `DetailDrawer`, `InfiniteScrollTriggerComponent`, `ToolTipComponent`, `PageHeader`, `ShareModal`).
- `src/containers/` — page-level components with business logic (currently a barrel; new orchestration components go here).
- `src/stores/` — Zustand stores. Domain stores live next to their components (e.g. [components/website/auth/libs/useAuthStore.ts](src/components/website/auth/libs/useAuthStore.ts), [components/ui/libs/useUiStore.ts](src/components/ui/libs/useUiStore.ts)). Reserve [src/stores/](src/stores/) for app-wide state ([useGlobalSettings.ts](src/stores/useGlobalSettings.ts)).
- `src/hooks/` — cross-cutting hooks (`useDebounce`, `useSyncedQueryState`, `useClarity`, etc.).
- `src/lib/` — `FetchHttpClient` (auth-refresh-aware HTTP client), `routes.ts`, `utils.ts`, `time.ts`, `nigerianLocations.ts`, `whatsapp.ts`, `config/`. Tests for pure modules sit beside them (`routes.test.ts`, `utils.test.ts`).
- `src/providers/` — top-level React providers (`client-wrapper.tsx`).
- `src/types/` — shared types and ambient `.d.ts` (clarity, zustand, zxcvbn).

## Path aliases

Defined in both [tsconfig.json](tsconfig.json) and [vitest.config.ts](vitest.config.ts) — keep them in sync. Available: `@/*`, `@app/*`, `@components/*`, `@3rdparty/*`, `@lib/*`, `@hooks/*`, `@stores/*`, `@styles/*`, `@icons/*`, `@app-types/*`, `@context/*`, `@assets/*`.

## Enum references, never free literals

Any value that has a defining enum or union type (verification/payment status, tier, currency, property type, etc. — declared in [src/types/models.ts](src/types/models.ts)) must be referenced via that enum/type in components, stores, and comparisons. Do not duplicate an enum value as a raw string literal. Backend is the source of truth for these values; keep the frontend enums in sync with the backend rather than inventing parallel literals. Exceptions: the type/enum definitions themselves, and tests asserting wire-string compatibility.

## FORM STABILITY (React Hook Form)

Ensure:
- all forms have stable validation states
- submit button disabled during submission
- no duplicate submissions allowed
- errors are consistently rendered
- implement idempotency when necessary

Ensure Zod validation errors are stable and testable.

## Testing

Vitest + jsdom. Tests sit beside the module they cover (`*.test.ts(x)`) — see [components/ui/schemas.test.ts](src/components/ui/schemas.test.ts), [lib/routes.test.ts](src/lib/routes.test.ts), [components/website/home.data.test.ts](src/components/website/home.data.test.ts). Vitest `globals: false` — import `describe`, `it`, `expect` explicitly.

When working on UI/UX, use the `frontend-design` skill. When implementing features, follow the `test-driven-development` skill (write the test first).

## UAT suite (Playwright, browser-driven acceptance)

`e2e/` is the browser UAT suite defined by [docs/uat-strategy.md](../docs/uat-strategy.md) — net-new *UI* coverage, distinct from `backend/scripts/e2e_drive_through.py` (which drives the API directly). Run it against a live local stack (strategy §9); it is **not** wired into CI yet.

```bash
# The suite runs against https://localhost:3000: a production build behind Caddy TLS for
# acceptance (docs/uat-strategy.md §9), or `pnpm dev:https` while authoring a spec.
pnpm e2e                                  # full six-engine matrix (parallel lane, then @serial lane)
UAT_ENGINES=chromium-desktop pnpm e2e     # one engine (fast local loop)
pnpm e2e specs/auth.spec.ts --grep UAT-AUTH-05
pnpm e2e:report                           # open the HTML report
```

- **The suite must run over HTTPS.** Session cookies are `__Host-` prefixed ⇒ `Secure`. Chromium treats `http://localhost` as a secure context and keeps them; **WebKit drops all four**, failing every authenticated scenario for a reason that cannot happen in production. `pnpm dev:https` reads a per-machine cert from `certificates/` (gitignored) — see strategy §9 for generating one without admin rights. Playwright sets `ignoreHTTPSErrors`, so a self-signed cert is fine.

- **Scenario ids.** Every test is `UAT-<AREA>-<n> · <business-observable outcome>` and carries its PRD reference in the describe/file docstring. Risk tags (`@P0`/`@P1`/`@P2`) go on the describe so `--grep @P0` scopes a partial run.
- **Tags choose engines and lanes** ([e2e/playwright.config.ts](e2e/playwright.config.ts)).
  - `@P0` runs on all six projects; `@P1`/`@P2` run only on `chromium-desktop` + `webkit-mobile`.
  - Tests run fully parallel (`UAT_WORKERS`, default 4 locally, 2 in CI).
  - A describe tagged **`@serial`** touches state other specs can see: the shared Mailpit inbox (`clearMailbox`), a seeded persona's data, or the seeded customer's drafts. `pnpm e2e` ([e2e/run-lanes.mjs](e2e/run-lanes.mjs)) runs two invocations: `UAT_LANE=parallel`, then `UAT_LANE=serial` (the `<engine>-serial` projects, one worker, reusing the first lane's seed and sessions via `UAT_REUSE_SEED`). The serial lane still runs when the parallel lane has failures, and either lane failing fails the run. Project dependencies would skip it instead, so don't chain the lanes that way. Always run the suite through `pnpm e2e`: a bare `playwright test` would run both lanes at once. Anything not tagged `@serial` must own its data (a `scenario` fixture), so it stays parallel-safe.
- **Seed once, bootstrap per spec.** [global-setup.ts](e2e/global-setup.ts) runs one `/dev/reset` + `/dev/seed` and logs every persona in, saving `storageState` per persona; specs consume it via `test.use({ storageState: storageStatePath(PERSONAS.X) })`. A spec needing a precondition the seed lacks creates it with the API helper in its own setup — never by depending on another spec's UI actions. For a verification at a lifecycle stage, use `buildScenario(ScenarioStage.X, tier)` ([helpers/scenario.ts](e2e/helpers/scenario.ts), backed by `POST /dev/scenario`): it returns a fresh customer and per-role agents (with credentials and task ids) that no other spec touches, so the spec is parallel-safe — log those accounts in with `loginViaUi` rather than reusing the seeded personas' `storageState`.
- **Fixtures before boilerplate.** New specs import `test`/`expect` from [e2e/fixtures.ts](e2e/fixtures.ts):
  - persona pages `customerPage`, `adminPage`, `opsAdminPage`, `financeAdminPage`, `agentPage(role)`, `anonPage`, and `pageAs(persona)` for any seeded persona;
  - `scenario(stage, { tier })` plus `pageFor(account)` to sign a scenario's fresh accounts in;
  - `sweep(Sweep.X)` for the admin sweep jobs;
  - `wa` for WhatsApp stub inbound/outbox/window/handoff, and `mail` for Mailpit.

  Scenario stages up to `RELEASED` are cumulative; `DISPUTED`/`RECHECK_REQUESTED`/`PAYOUT_READY` branch off a released case. Fixture callbacks are named `provide`, because React's hook lint rules flag a parameter named `use`.
- **Helpers before new plumbing.** [e2e/helpers/](e2e/helpers/):
  - `api()`/`anonymousApi()`: CSRF-aware HTTP for preconditions **only** — never for assertions;
  - `loginViaUi`; `goto`/`waitReady`/`expectAuthenticated` (window hooks); `readSeed`;
  - `waitForEmail`/`extractLinkFromEmail` (Mailpit); `expectNoA11yViolations`;
  - [helpers/ui.ts](e2e/helpers/ui.ts): `tableRow`, `rowAction`, `drawer`/`closeDrawer`, `expectForbidden`, `stubPay`, `downloadAndRead`, and the two layout-aware shell helpers `signOut` / `openNavItem` (the shell renders one nav for the desktop rail and one in the mobile drawer, so a bare `getByRole("link")` matches twice and the mobile copy is parked off-screen until opened).

  `helpers/ui.ts` imports DataTable anchors from `components/ui/table/testIds.ts`, the same module the component renders from, so selectors never drift.
- **Deterministic waits only.** `waitReady(page)` (`__app_ready__`) and web-first assertions — never `waitForTimeout`.
- **A11y is an acceptance criterion, not a separate pass.** Call `expectNoA11yViolations(page)` on every page state a scenario visits; serious/critical axe violations fail the scenario. `A11Y_BASELINE` in [helpers/a11y.ts](e2e/helpers/a11y.ts) is tracked, justified debt to burn down — prefer fixing the violation.
- **Assert business-observable outcomes** through rendered UI (visible label, state, artifact, email), never "no error thrown".
- **A11y checks find pre-existing debt when a spec visits a page nothing else covered.** The WhatsApp specs were the first to run axe on `/` and `/sample-report` and surfaced serious contrast failures there — including the sample report's legal footer. Fix the violation rather than scoping the check or growing `A11Y_BASELINE`; decorative *text* is the one case where the fix is to stop it being text (render it as a CSS pseudo-element), because `aria-hidden` alone still leaves it visible and failing.
- Suites: `auth`, `session` (§7.2 — silent refresh, lost session back to where the user was, revoked device, sign-out; clearing the access-cookie pair is how a spec simulates an expired access token), `dev-contracts`, `golden-path`, `whatsapp-widget` (§26.4.1 — reachable everywhere, absent in the payment flow), `wa-handoff` (§26.4.2/§26.5 — a link lands in context, a forwarded copy is dead, the holder can still reload). `wa-handoff` mints links through `POST /dev/whatsapp/handoff-token` with `anonymousApi()`: the landing needs no session, which is the property under test. `status-pages` (404/403: a working way out for every visitor, each persona's 403 aimed at their own dashboard, axe on both), `chat` (§16, §26.6–§26.10, D89–D93 — the web assistant's inline welcome and deferred turn, a linked customer's WhatsApp thread at `/portal/chat` and its read-only state after unlink, "Seen", delivery ticks driven through `wa.status`, the admin Conversations facets, and hand-back on a per-case thread) is `@P1`, so it runs on `chromium-desktop` and `webkit-mobile` only.
- **Coverage stops at the S7 channel surfaces, and that is a known hole rather than a decision.** The suites reach the widget, the handoff landings and (`chat`) the messaging surfaces incl. `AssistantModeBanner`; the surfaces still without browser coverage — the `/admin/analytics` channel tab, `DelegatePanel`, the two §26.4.6 opt-in controls and `/wa/intake/[token]` — have backend drive-through coverage but no browser coverage, so nothing here would notice if one of them stopped rendering. A new spec for any of them is worth more than another suite elsewhere.
- **Chat specs: three traps.** (1) Never put `Date.now()` (or any 9+ digit run) in a message body — the fraud scan's PHONE rule HELDs it, and a held message never reaches the admin inbox; use a short UUID slice. (2) The admin inbox search is debounced (300ms) and every scenario customer is named "Ada Scenario": locate rows with `.filter({ hasText: <email|number> })`, never a bare row count. (3) The stub outbox records recipients as Meta wa_ids — digits, no `+` — so pass `e164.replace("+", "")` to `wa.outbox`. Muted chat text is `text-gray-600`: `gray-500` is 4.39:1 on the app's `#f3f4f5` surfaces and fails AA.
- **Wait for hydration before typing, and judge only against a build.** A form's first field can lose what is
  typed into it: the server-rendered input accepts text, then React hydrates, and the controlled input is reset to
  its empty `defaultValue` — the box comes back blank with "required" showing while later fields keep their values.
  It is loud against `pnpm dev:https` (WebKit especially) and rare but real against a production build, so
  `waitForHydration(page, testId)` (`e2e/helpers/app.ts`, waits for React's `__reactProps$` key on the node) goes
  before the first `fill` of every form. Deliberately **not** a refill-until-it-sticks loop: that would absorb a
  genuine regression. docs/uat-strategy.md §9 is the rule — author specs against the dev server, judge green/red
  only against `pnpm build` + the standalone server behind `e2e/tls/Caddyfile`.
- **WebKit can drop a click on a control that has just swapped in.** Seen on the signup step's `Verify` button in CI and locally (reproducible only right after the drive-through, and not under instrumentation): Playwright reports the click performed on a visible, enabled, stable button, yet no request leaves the page and the button never enters its sending state. A user simply taps again. `openOtpDialog` repeats the click only while it has provably had **no** effect; any effect — sending, an error, the dialog — ends the retrying and decides the outcome, so a send that fails or hangs still fails. Don't widen this into retrying after an outcome, which would hide a real regression. CI uploads the Playwright report on every run, so a recurrence leaves its first-attempt trace.
- **Let animations finish before an axe scan.** Axe reads computed colours, so a scan taken mid-transition (a
  disabled button fading in, a dialog easing open) reports a blended contrast ratio that neither the start nor the
  end state has. `expectNoA11yViolations` waits for finite animations first; endless ones (a spinner) are left running.
- Artifacts (`e2e/.auth/`, `playwright-report/`, `test-results/`) are gitignored; specs and helpers are committed.

## Automation determinism (permanent rules — do not remove)

### data-testid policy
Auth form elements carry stable `data-testid` selectors for Playwright automation. **Never remove them.** Naming scheme:

| Component | Selector |
|---|---|
| Login form | `login-form`, `login-email`, `login-password`, `login-password-toggle`, `login-submit`, `login-error` |
| Signup step 1 | `signup-basics-form`, `signup-first-name`, `signup-last-name`, `signup-email`, `signup-password`, `signup-basics-submit` |
| Signup stepper | `signup-stepper` |
| Verify step | `verify-form`, `verify-submit`, `verify-back` |
| Forgot password | `forgot-form`, `forgot-email`, `forgot-submit` |
| Reset password | `reset-password-form`, `reset-password-password`, `reset-password-confirm`, `reset-password-submit` |
| OAuth buttons | `oauth-google`, `oauth-apple`, `oauth-facebook` |
| DataTable (every admin table) | `datatable-row` + `data-row-id`, `datatable-row-actions`, `datatable-action-{label-slug}`, `datatable-prev`, `datatable-next` — defined once in `components/ui/table/testIds.ts` |
| DetailDrawer | `detail-drawer` (`role="dialog"`, `aria-modal`, labelled by its title), `detail-drawer-close` |
| App shell sign-out | `user-menu`, `user-menu-signout` (desktop top nav); `sidebar-open`, `sidebar-signout` (mobile drawer) — drive through `signOut(page)` in `e2e/helpers/ui.ts`, which picks the layout |
| Session recovery | `session-recovery-overlay`, `session-recovery-attempt`, `session-signin-now` |

When adding new forms, follow the same `{flow}-{element}` pattern.

### Auth hydration
`ClientWrapperProvider` must **not** return null while waiting for client mount. Do not add `if (!mounted) return null` — it causes a blank render flash and breaks Playwright's `waitForLoadState`. Use `suppressHydrationWarning` on wrapper elements if needed instead.


## UX & Interaction Standards

See [.claude/ux-standards.md](.claude/ux-standards.md) for tooltip rules, feedback states, form validation, empty states, cursor behavior, accessibility requirements, and PR checklist.
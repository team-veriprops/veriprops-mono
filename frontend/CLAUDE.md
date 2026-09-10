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

Secrets are Doppler-managed (project `veriprops-frontend`, configs `prd`/`stg`/`dev`) and are injected by `deploy.yml` itself: the environment-scoped `DOPPLER_TOKEN_FRONTEND` service token selects the config, and every key ships as deployment-scoped `--build-env`/`--env` flags for dev, staging **and** production (production's file base is `.env.production`, auto-loaded by `next build`). There is **no Doppler→Vercel sync and no dashboard env vars** — staging and dev can hold different secret values, rollbacks restore the env a deployment shipped with, and a rotated Doppler value takes effect on the next deploy. The only live frontend secret (`EDGE_AUTH_SECRET`) is a single zone-wide value shared with the backend and the Cloudflare Transform Rule. Never store a *blank* secret value in a Doppler config — it overrides the file placeholder and (for `EDGE_AUTH_SECRET`) silently disables the trusted-edge check. **Never put a secret in a `NEXT_PUBLIC_*` var** (build-time inlined into the bundle). The backend hygiene guard (`backend/test/unit/app/config/test_env_hygiene.py`) scans all five committed files and fails on any credential-shaped value. Runtime flags still come from the backend's `/config/public`, not new env vars.

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
- Add structured data with `<JsonLd data={...} />` ([src/components/seo/JsonLd.tsx](src/components/seo/JsonLd.tsx)) using the builders in `seo.ts` (`organizationJsonLd`, `websiteJsonLd`, `faqJsonLd`, `legalDocumentJsonLd`).
- Keep [src/app/sitemap.ts](src/app/sitemap.ts) and [src/app/robots.ts](src/app/robots.ts) current: public marketing + legal routes are crawlable; `/portal`, `/admin`, `/agents`, `/account`, `/auth` are disallowed. VID-lookup pages pass `noindex` until `COMPLETED`.

## WhatsApp channel surfaces (PRD §26)

- **The widget** ([components/website/WhatsAppWidget.tsx](src/components/website/WhatsAppWidget.tsx)) mounts once in `ClientWrapperProvider`, so it rides every surface without per-layout wiring. It is `position: fixed` — that is what makes "zero CLS" structural rather than a promise — and it renders **nothing** until `/config/public` supplies the number: the number is the customer's anti-impersonation anchor (§26.1.2), so there is deliberately no hardcoded fallback. It suppresses itself inside the payment flow (§26.4.1).
- **Page codes** ([lib/whatsapp.ts](src/lib/whatsapp.ts)) are the one thing here the backend does not own — they describe frontend routes it does not model. Explicit entries win; anything else derives from the first path segment, so a new page stays attributable without a table edit (§26.10). Payment-flow suppression matches `PAYMENT_FLOW_PATH_PATTERNS` in [routes.ts](src/lib/routes.ts), kept beside the route builders it mirrors.
- **Handoff landings** (`/wa/{pay,upload,report}/[token]`, [components/website/handoff/](src/components/website/handoff/)) are public by design — the token is the authorization, so they must stay out of `PROTECTED_PREFIXES`. Redemption happens in an **effect, never during render**: it is single-use, and WhatsApp fetches the URL to build its link preview. The page must acknowledge the case it picked up (silent context loss is a spec violation) and must **never** explain why a link failed — expired, spent, and forged are one state. Only `pay` completes there; `upload`/`report` hand into the authenticated portal (D50).
- **Source labels.** WhatsApp and the website feed one admin console, so a thread/message carries `channel`/`source` and renders [ChannelBadge](src/components/chat/ChannelBadge.tsx). Web is the unlabelled default, so the badge means "notice this" rather than decorating every row. Three per-message markers ride the same principle, each rendered only when its field is set: `unofficialMedia` ("not evidence" — §26.1.6's rule, on every chat-borne image, document or voice note), `mediaKind` (an audio marker for a voice note), and `pendingChannelDelivery` (an agent reply that is in the thread but has not left over WhatsApp yet, because it was typed outside Meta's 24-hour window). The last one matters most: without it an agent believes their message sent. All three are backend-derived — never recompute them client-side — and `mediaKind` renders through `humanizeEnumLabel`, never as a raw enum string.
- **The §26.7 template registry** lives at `/admin/config/whatsapp-templates` ([WhatsAppTemplates](src/components/admin/config/WhatsAppTemplates.tsx), `CONFIGURE_SYSTEM`) and is **read-plus-sync, never editable**: the definitions are code-owned on the backend and the status is Meta's, so an input here would let the page claim something the app does not do. `NOT_FOUND` is ours rather than Meta's — declared but never submitted — and is the state the §26.11 launch gate actually asks about, so it renders as needing attention, not as a failure.
- **Account linking** (§26.4.4) lives at `/account/whatsapp` ([WhatsAppLinkSettings](src/components/account/WhatsAppLinkSettings.tsx)) — its own page rather than a section of `/account/linked`, which is OAuth-provider specific. Only `WhatsAppLinkStatus.ACTIVE` means linked: a `PENDING` row carries a number but grants nothing, so never infer "linked" from a number being present. `/wa/link/[token]` is the one `/wa/*` landing inside `PROTECTED_PREFIXES` (`WA_LINK_PREFIX` in [routes.ts](src/lib/routes.ts)) — the token says which number is being claimed, the session says which account claims it. That page **must never send a number**: it posts the token alone, so a signed-in attacker cannot have a code delivered to a number the bot never messaged.
- **The admin messaging console is one page, two tabs** (`/admin/messages` → [AdminMessagesTabs](src/components/chat/AdminMessagesTabs.tsx)): the §11.2 hold-review queue and the WhatsApp inbox ([AdminWhatsAppInboxContainer](src/components/chat/AdminWhatsAppInboxContainer.tsx)). Decision K puts every surface in one console, so don't split them across routes. The inbox filters the ordinary `/chat/conversations` list to `channel === WHATSAPP` and posts through `useConversationSendMutation` (by conversation id) — a §26.8 enquiry thread often has no verification behind it, so the verification-keyed send paths don't apply.
- **[WhatsAppBotModeBanner](src/components/chat/WhatsAppBotModeBanner.tsx) is not decoration.** A thread goes sticky-`HUMAN` the moment an agent replies (D57) and stays there until it is handed back — and that state is **invisible from the message list**, where a silenced bot looks exactly like a working one. The banner is the only way a person can see it or undo it, so any surface that can reply to a WhatsApp thread must render it. It is admin-only (`CONFIGURE_SYSTEM` endpoints, and a 403 hard-navigates to `/forbidden`), so never mount it on a customer surface. It carries a second invisible state for the same reason: `windowOpen` says whether Meta's 24-hour service window is still open, which an agent needs **before** typing — outside it their words are queued behind a `window_reopen` nudge rather than delivered. Both facts come from the one `GET /admin/whatsapp/bot/sessions/{phone}` call the banner already makes, so showing them costs no extra request.
- **`/wa/intake/[token]`** ([WaIntakeLanding](src/components/website/handoff/WaIntakeLanding.tsx)) is the second `/wa/*` landing inside `PROTECTED_PREFIXES` (`WA_INTAKE_PREFIX`), for the same reason as linking: the token carries a *conversation*, the session says whose draft its answers become (D69). It redeems in an **effect, never during render** (single-use, and WhatsApp fetches the URL for its preview card), then `router.replace`s into the existing submission wizard — the seeded draft is what the wizard resumes, so there is no chat-specific consent or payment surface to keep in sync. A dead link gets the same one indistinguishable state as every other handoff landing.
- **[WhatsAppContinueButton](src/components/portal/WhatsAppContinueButton.tsx)** is the web→chat half of continuation (§26.4.3, D58). `waContinueUrl` pre-fills the `VP-…` reference, which the bot matches on the customer's literal words — without it the customer must go and find a reference before the chat can help. Like the widget, it renders **nothing** without a configured number: no hardcoded fallback, ever (§26.1.2).
- **The two §26.4.6 opt-ins are one shared control on two payment surfaces** ([WhatsAppOptInControls](src/components/shared/whatsapp/WhatsAppOptInControls.tsx), D76). It renders on the authenticated pay screen ([PayContainer](src/components/portal/submission/PayContainer.tsx)) **and** on the `/wa/pay/[token]` landing, because the customer who arrived from chat is asked there or nowhere — and §26.10 counts the opt-in rate as the channel's consent asset. It lives in `shared/` for exactly that reason: the two surfaces write through different endpoints (one session-authenticated, one grant-scoped), so only the markup and the words are shared, and the two cannot drift into asking different questions. Three properties are requirements, not styling: they are **two** controls (bundling would leave the marketing consent unevidenced), they render **unticked** from the backend's "no record" state (a pre-ticked box is not consent), and they are written **on toggle** rather than on payment success — the tick is the consent act, and a failed card must not discard it. Revocation lives on `/account/whatsapp` ([WhatsAppConsentSettings](src/components/account/WhatsAppConsentSettings.tsx)), which is the **only** place marketing consent can be given back: a chat `START` restores progress updates alone (D64).
- **[DelegatePanel](src/components/portal/verifications/DelegatePanel.tsx) sits between "Your agents" and "Evidence" on the case page**, and that position is the grant rendered: with the people on the case, ahead of the material a §26.4.5 delegate must never see. Its copy states the limits before the buyer uses it — one person, status updates only, never documents or the report — because a buyer who believes they are sharing the report is surprised twice, once here and once when their delegate asks why they cannot open it. The awaiting-code state is rendered plainly rather than as a spinner: it lasts as long as it takes the buyer to reach the person and read the code back, and hiding it makes them nominate again because nothing appeared to happen. Confirmation posts the **code alone** — which number is being confirmed comes from the authorization already on the case, so a browser can never redirect a code to a number nobody nominated.
- **Channel analytics is a tab on `/admin/analytics`, not a route** ([WhatsAppChannelAnalytics](src/components/admin/analytics/WhatsAppChannelAnalytics.tsx), D86). Same reasoning as `AdminMessagesTabs`: the platform funnel and the channel funnel are the same question asked of two surfaces, and separate routes would make the channel look like a separate product. It reuses [StatCard](src/components/ui/StatCard.tsx) and [MiniBarBreakdown](src/components/ui/MiniBarBreakdown.tsx) — the **no external charting dependency** rule stated at the top of `AdminAnalytics.tsx` holds for this tab too; `recharts` is in `package.json` but only the untouched shadcn wrapper imports it. Three things here are requirements rather than layout: every **rate renders the counts behind it** (60% over three conversations and over three hundred call for opposite decisions, and a percentage alone cannot tell them apart); the **Meta quality rating renders its sync age** (a GREEN nobody could refresh for a week is a different fact from this morning's, and `syncError` is what distinguishes them); and a **never-synced rating is never toned as healthy** — §26.11 treats it as a launch gate, so the absence of Meta's verdict must not read as a clean bill of health. Page codes keep their hyphens through `humanizeEnumLabel`, deliberately: they are identifiers to match against [lib/whatsapp.ts](src/lib/whatsapp.ts), not status labels.

## Backend-served content & public flags

- Legal pages render content the backend owns: the dynamic `/legal/[slug]` route fetches via [src/lib/legal.server.ts](src/lib/legal.server.ts) (`fetchLegalDocument`/`fetchLegalDocuments` → `/api/users/auth/consents/documents/...`) and renders Markdown through `LegalDocument`. Do not hardcode legal prose on the frontend.
- Read runtime flags from the backend, not from `NEXT_PUBLIC_*`. `usePublicConfigQuery()` exposes `/config/public` (e.g. `phoneVerificationEnabled`, which drives whether the signup flow shows the phone-verification step).
- The `/account/*` security surface (security log, devices, linked accounts, password) lives under `src/app/account/` on `AppShell`; the `PortalSwitcher` in the shell shows the cross-portal badge for multi-persona users.

## Styling

All styling is `className` (Tailwind v4 utilities, generated from [src/styles/theme.css](src/styles/theme.css)'s CSS-first `@theme inline` config) — never the `style` prop. Conditional styling uses `cn()` from [src/lib/utils.ts](src/lib/utils.ts) to merge a base class string with per-branch classes, never a `style={condition ? {...} : {...}}` object. Inline `style` is reserved for two narrow, permanent exceptions:

- **Runtime-computed numeric values** that can't be expressed as a static class: bar-fill/column widths derived from data ratios ([MiniBarBreakdown.tsx](src/components/ui/MiniBarBreakdown.tsx), [AdminAnalytics.tsx](src/components/admin/analytics/AdminAnalytics.tsx)), the sidebar slide transform in [AppShell.tsx](src/components/ui/AppShell.tsx), and per-column pixel widths in [DataTable.tsx](src/components/ui/table/DataTable.tsx).
- **Vendored third-party CSS-variable contracts** in `src/components/3rdparty/ui/` — `sidebar.tsx`, `sonner.tsx`, and `chart.tsx` theme Radix/Sonner/Recharts by injecting CSS custom properties via `style={{ "--foo": value } as React.CSSProperties}`, which is the documented way to theme those libraries; `progress.tsx`'s Radix fill uses `style={{ transform: ... }}`, the standard Radix animation pattern.

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
- **Full-screen wizards** (submission, agent apply) share [src/components/ui/wizard/WizardOverlay.tsx](src/components/ui/wizard/WizardOverlay.tsx) — a stepper + footer shell; keep step content in per-step components and thread a `testIdPrefix`. Pass `closable={false}` to hide the close control for a compulsory flow the user cannot dismiss (e.g. the agent-onboarding gate below) — default is closable.
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
pnpm dev:https                            # REQUIRED — the suite runs against https://localhost:3000
pnpm e2e                                  # full six-engine matrix
UAT_ENGINES=chromium-desktop pnpm e2e     # one engine (fast local loop)
pnpm e2e specs/auth.spec.ts --grep UAT-AUTH-05
pnpm e2e:report                           # open the HTML report
```

- **The suite must run over HTTPS.** Session cookies are `__Host-` prefixed ⇒ `Secure`. Chromium treats `http://localhost` as a secure context and keeps them; **WebKit drops all four**, failing every authenticated scenario for a reason that cannot happen in production. `pnpm dev:https` reads a per-machine cert from `certificates/` (gitignored) — see strategy §9 for generating one without admin rights. Playwright sets `ignoreHTTPSErrors`, so a self-signed cert is fine.

- **Scenario ids.** Every test is `UAT-<AREA>-<n> · <business-observable outcome>` and carries its PRD reference in the describe/file docstring. Risk tags (`@P0`/`@P1`/`@P2`) go on the describe so `--grep @P0` scopes a partial run.
- **Seed once, bootstrap per spec.** [global-setup.ts](e2e/global-setup.ts) runs one `/dev/reset` + `/dev/seed` and logs every persona in, saving `storageState` per persona; specs consume it via `test.use({ storageState: storageStatePath(PERSONAS.X) })`. A spec needing a precondition the seed lacks creates it with the API helper in its own setup — never by depending on another spec's UI actions.
- **Helpers before new plumbing.** [e2e/helpers/](e2e/helpers/): `api()`/`anonymousApi()` (CSRF-aware HTTP for preconditions **only** — never for assertions), `loginViaUi`, `goto`/`waitReady`/`expectAuthenticated` (window hooks), `readSeed`, `waitForEmail`/`extractLinkFromEmail` (Mailpit), `expectNoA11yViolations`.
- **Deterministic waits only.** `waitReady(page)` (`__app_ready__`) and web-first assertions — never `waitForTimeout`.
- **A11y is an acceptance criterion, not a separate pass.** Call `expectNoA11yViolations(page)` on every page state a scenario visits; serious/critical axe violations fail the scenario. `A11Y_BASELINE` in [helpers/a11y.ts](e2e/helpers/a11y.ts) is tracked, justified debt to burn down — prefer fixing the violation.
- **Assert business-observable outcomes** through rendered UI (visible label, state, artifact, email), never "no error thrown".
- **A11y checks find pre-existing debt when a spec visits a page nothing else covered.** The WhatsApp specs were the first to run axe on `/` and `/sample-report` and surfaced serious contrast failures there — including the sample report's legal footer. Fix the violation rather than scoping the check or growing `A11Y_BASELINE`; decorative *text* is the one case where the fix is to stop it being text (render it as a CSS pseudo-element), because `aria-hidden` alone still leaves it visible and failing.
- Suites: `auth`, `dev-contracts`, `golden-path`, `whatsapp-widget` (§26.4.1 — reachable everywhere, absent in the payment flow), `wa-handoff` (§26.4.2/§26.5 — a link lands in context, a forwarded copy is dead, the holder can still reload). `wa-handoff` mints links through `POST /dev/whatsapp/handoff-token` with `anonymousApi()`: the landing needs no session, which is the property under test.
- **Coverage stops at the S7 channel surfaces, and that is a known hole rather than a decision.** The five suites reach the widget and the handoff landings; the surfaces added afterwards — the `/admin/analytics` channel tab, `DelegatePanel`, the two §26.4.6 opt-in controls, `/wa/intake/[token]`, and `WhatsAppBotModeBanner` — have backend drive-through coverage but no browser coverage, so nothing here would notice if one of them stopped rendering. Several are exactly the kind that fail silently: the bot-mode banner *is* the only visible sign of a state the message list cannot show. A new spec for any of them is worth more than a sixth suite elsewhere.
- Artifacts (`e2e/.auth/`, `playwright-report/`, `test-results/`) are gitignored; specs and helpers are committed.

## Automation determinism (permanent rules — do not remove)

### data-testid policy
Auth form elements carry stable `data-testid` selectors for Playwright automation. **Never remove them.** Naming scheme:

| Component | Selector |
|---|---|
| Login form | `login-form`, `login-email`, `login-password`, `login-password-toggle`, `login-submit` |
| Signup step 1 | `signup-basics-form`, `signup-first-name`, `signup-last-name`, `signup-email`, `signup-password`, `signup-basics-submit` |
| Signup stepper | `signup-stepper` |
| Verify step | `verify-form`, `verify-submit`, `verify-back` |
| Forgot password | `forgot-form`, `forgot-email`, `forgot-submit` |
| Reset password | `reset-password-form`, `reset-password-password`, `reset-password-confirm`, `reset-password-submit` |
| OAuth buttons | `oauth-google`, `oauth-apple`, `oauth-facebook` |

When adding new forms, follow the same `{flow}-{element}` pattern.

### Auth hydration
`ClientWrapperProvider` must **not** return null while waiting for client mount. Do not add `if (!mounted) return null` — it causes a blank render flash and breaks Playwright's `waitForLoadState`. Use `suppressHydrationWarning` on wrapper elements if needed instead.


## UX & Interaction Standards

See [.claude/ux-standards.md](.claude/ux-standards.md) for tooltip rules, feedback states, form validation, empty states, cursor behavior, accessibility requirements, and PR checklist.
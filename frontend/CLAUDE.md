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
- **Full-screen wizards** (submission, agent apply) share [src/components/ui/wizard/WizardOverlay.tsx](src/components/ui/wizard/WizardOverlay.tsx) — a stepper + footer shell; keep step content in per-step components and thread a `testIdPrefix`.

## Layout

- `src/app/` — App Router. Top-level segments are isolated user surfaces:
  - `(website)/` — public marketing + auth (login, signup, OAuth, password flows) + account.
  - `portal/` — authenticated user area.
  - `admin/` — internal admin.
  - `agents/` — agent-facing area.
- `src/components/{surface}/` — components grouped by the surface they serve (`website/`, `portal/`, `admin/`, `agents/`, `account/`, `nav/`, plus shared `ui/` and `3rdparty/`). Keep components close to the surface that owns them; promote into `ui/` only when reused by 2+ surfaces.
- `src/components/ui/` — primitives + Radix wrappers (`AsyncStateComponent`, `table`, form helpers `form/`, `verified_input/`, `upload/`, `BrandLogo`, `CopyText`, `DetailDrawer`, `InfiniteScrollTriggerComponent`, `ToolTipComponent`, `PageHeader`, `ShareModal`).
- `src/containers/` — page-level components with business logic (currently a barrel; new orchestration components go here).
- `src/stores/` — Zustand stores. Domain stores live next to their components (e.g. [components/website/auth/libs/useAuthStore.ts](src/components/website/auth/libs/useAuthStore.ts), [components/ui/libs/useUiStore.ts](src/components/ui/libs/useUiStore.ts)). Reserve [src/stores/](src/stores/) for app-wide state ([useGlobalSettings.ts](src/stores/useGlobalSettings.ts)).
- `src/hooks/` — cross-cutting hooks (`useDebounce`, `useSyncedQueryState`, `useClarity`, etc.).
- `src/lib/` — `FetchHttpClient` (auth-refresh-aware HTTP client), `routes.ts`, `utils.ts`, `time.ts`, `nigerianLocations.ts`, `uploadService.ts`, `config/`. Tests for pure modules sit beside them (`routes.test.ts`, `utils.test.ts`).
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

## Automation determinism (permanent rules — do not remove)

### data-testid policy
Auth form elements carry stable `data-testid` selectors for Playwright automation. **Never remove them.** Naming scheme:

| Component | Selector |
|---|---|
| Login form | `login-form`, `login-email`, `login-password`, `login-password-toggle`, `login-submit` |
| Signup step 1 | `signup-basics-form`, `signup-first-name`, `signup-last-name`, `signup-email`, `signup-password`, `signup-basics-submit` |
| Signup stepper | `signup-stepper` |
| Verify step | `verify-form`, `verify-submit`, `verify-back` |
| OAuth buttons | `oauth-google`, `oauth-apple`, `oauth-facebook` |

When adding new forms, follow the same `{flow}-{element}` pattern.

### Auth hydration
`ClientWrapperProvider` must **not** return null while waiting for client mount. Do not add `if (!mounted) return null` — it causes a blank render flash and breaks Playwright's `waitForLoadState`. Use `suppressHydrationWarning` on wrapper elements if needed instead.


## UX & Interaction Standards

See [.claude/ux-standards.md](.claude/ux-standards.md) for tooltip rules, feedback states, form validation, empty states, cursor behavior, accessibility requirements, and PR checklist.
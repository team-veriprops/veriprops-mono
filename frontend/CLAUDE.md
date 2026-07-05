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

`/api/*` requests are rewritten to `${API_BASE_URL}/api/*` by [next.config.ts](next.config.ts). `API_BASE_URL` is server-only (read from [src/lib/config/server.ts](src/lib/config/server.ts), which throws if imported on the client). Public env vars (`NEXT_PUBLIC_*`) live in [src/lib/config/public.ts](src/lib/config/public.ts) — keep them split.

## Auth Guard

- Use Next.js `proxy.ts` to control access to protected routes.

  * Centralize route protection in `proxy.ts` rather than duplicating auth checks across pages or layouts.
  * Validate authentication state (session, token, or cookie) in `proxy.ts` before allowing access to protected routes.
  * Redirect unauthenticated users to the sign-in page.
  * Redirect authenticated users away from guest-only routes (for example: sign-in, sign-up) when appropriate.
  * Keep route matching explicit and maintainable by clearly defining protected, public, and guest-only route groups.
  * `proxy.ts` should handle **access control only**; page-level authorization and business rules should remain in the application layer.

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
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


## Layout

- `src/app/` — App Router. Top-level segments are isolated user surfaces:
  - `(website)/` — public marketing + auth (login, signup, OAuth, password flows).
  - `portal/` — authenticated user area.
  - `admin/` — internal admin.
  - `agents/` — agent-facing area.
- `src/components/{surface}/` — components grouped by the surface they serve (`website/`, `portal/`, `admin/`, `agents/`, `account/`, `nav/`, plus shared `ui/` and `3rdparty/`). Keep components close to the surface that owns them; promote into `ui/` only when reused by 2+ surfaces.
- `src/components/ui/` — primitives + Radix wrappers (`AsyncStateComponent`, `DataTable`, form helpers, `verified_input/`, `upload/`).
- `src/containers/` — page-level components with business logic (currently a barrel; new orchestration components go here).
- `src/stores/` — Zustand stores. Domain stores live next to their components (e.g. [components/website/auth/libs/useAuthStore.ts](src/components/website/auth/libs/useAuthStore.ts), [components/ui/libs/useUiStore.ts](src/components/ui/libs/useUiStore.ts)). Reserve [src/stores/](src/stores/) for app-wide state ([useGlobalSettings.ts](src/stores/useGlobalSettings.ts)).
- `src/hooks/` — cross-cutting hooks (`useDebounce`, `useSyncedQueryState`, `useClarity`, etc.).
- `src/lib/` — `FetchHttpClient` (auth-refresh-aware HTTP client), `routes.ts`, `utils.ts`, `time.ts`, `nigerianLocations.ts`, `uploadService.ts`, `config/`. Tests for pure modules sit beside them (`routes.test.ts`, `utils.test.ts`).
- `src/providers/` — top-level React providers (`client-wrapper.tsx`).
- `src/types/` — shared types and ambient `.d.ts` (clarity, zustand, zxcvbn).

## Path aliases

Defined in both [tsconfig.json](tsconfig.json) and [vitest.config.ts](vitest.config.ts) — keep them in sync. Available: `@/*`, `@app/*`, `@components/*`, `@3rdparty/*`, `@lib/*`, `@hooks/*`, `@stores/*`, `@styles/*`, `@icons/*`, `@app-types/*`, `@context/*`, `@assets/*`.

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

When adding new auth-related forms, follow the same `{flow}-{element}` pattern.

### Auth hydration
`ClientWrapperProvider` must **not** return null while waiting for client mount. Do not add `if (!mounted) return null` — it causes a blank render flash and breaks Playwright's `waitForLoadState`. Use `suppressHydrationWarning` on wrapper elements if needed instead.


# CLAUDE.md

Veriprops is a property verification platform. Monorepo with two deployable apps that talk over HTTP:

- [backend/](backend/) — FastAPI service (Python 3.12, MySQL, async SQLAlchemy, Alembic). See [backend/CLAUDE.md](backend/CLAUDE.md).
- [frontend/](frontend/) — Next.js 16 App Router, React 19, TypeScript. See [frontend/CLAUDE.md](frontend/CLAUDE.md).

Product context lives in [PRD.md](PRD.md) — read the relevant section before designing features that touch verification, agent onboarding, or reports.

## Running both ends

The frontend rewrites `/api/*` to the backend (see [frontend/next.config.ts](frontend/next.config.ts)), so for any feature that crosses the boundary, run both:

```bash
# terminal 1 — backend on :8000
cd backend && python veriprops.py

# terminal 2 — frontend on :3000
cd frontend && pnpm dev
```

Frontend reads `API_BASE_URL` (server-only) from its env to build the proxy target. If you change ports, update both ends.

## Cross-cutting conventions

- **API casing.** Backend Pydantic models serialize as camelCase (via `to_camel` alias generator in [appodus_utils/db/models.py](backend/main/appodus_utils/db/models.py)) but Python code stays snake_case. Frontend types are camelCase — don't add a transformation layer.
- **Backend API and Frontend Service Contract** Every call to the backend is proxied through Nextjs reverse proxy, no call reaches the backend directly. The backend API and the frontend services consuming the APIs should be maintained always in synch. When refactoring/adding/renaming an endpoint/service class, change both files in the same PR. 
- **Package managers.** Frontend is `pnpm` (lockfile committed); never use `npm` or `yarn`. Backend is plain `pip` against `requirements.txt`, but `test-requirements.txt` during test as it included extra test dependencies.
- **Session Propagation.** The auth session is propagated through a HttpOnly JWT cookie created by the backend.
- **Path handling.** Use `path.join` / `pathlib` / POSIX-safe APIs — never hardcode `\` or `/` separators.
- **Real-time channel**: SSE (live dashboard updates, notifications, metrics counters, audit feed), WS (collaborative workflow,chat,presence,two-way realtime commands).

## Pagination Convention
Every list that can grow, should be implemented a page as follows:
1. **Backend** -  The API must accept page (zero index) and page_size params, defaulted to 0 and 10 respectively. The API should also return an Object of Page[T], implemented in the file `backend\main\appodus_utils\db\models.py`. The GenericRepo returns this Object through get_page
2. **Frontend** - The frontend receives the value as an Object of Page<T>, implemented in the file `frontend\src\types\models.ts`. It must also implement paginated rendering of the values. For main Table in the Admin pages, use our existing DataTable implemented here `frontend\src\components\ui\DataTable.tsx`

## Workflow

When adding a feature, write a short plan and confirm with the user before coding, write tests first, then implement. Update the relevant `CLAUDE.md` if a new pattern emerges that future agents would otherwise have to re-derive.

### Non-negotiable rule
1. No Frontend/Backend duplicate implementations. 
2. As much as possible, deliver all implementation as full vertical slices (backend domains + Alembic migrations + tests + frontend ) so each phase ships demoably end-to-end.
3. For any change/refactor, make sure to also refactor the whole codebase, including all their references and related implementations; no feature should be ophaned.
4. After each code change, refactor all existing tests, run the tests, and fix defects. Also confirm the app builds and lints.
5. No facts should be derived on the frontend, delegate such tasks to the backend.
6. When investigating the app ui, use playwright-cli skills.

## Automation determinism

The codebase ships a deterministic foundation for autonomous QA (Playwright + Claude Code). These rules are permanent — do not remove them:

- **OTP_MODE contract.** `OTP_MODE=deterministic` means all OTP calls return `TEST_OTP` (654123). `OTP_MODE=random` generates real random codes. `ENVIRONMENT=test` requires `deterministic`. `ENVIRONMENT=prod` requires `random`. Startup fails otherwise. Never compare `ENVIRONMENT` string to detect OTP behaviour — always read `OTP_MODE`.
- **Dev endpoints.** `POST /dev/reset` and `POST /dev/seed` are available in all non-production environments. They are production-gated twice: the router only mounts in non-prod, and `_require_non_prod()` returns 404 in production. Never remove these guards.
- **Mailpit SMTP.** In dev/local/test environments, email is captured by Mailpit (SMTP on `localhost:1025`). The `SmtpEmailProvider` hard-fails in production and staging. Do not add `EMAIL_PROVIDER` settings — the router selects SMTP automatically based on `ENVIRONMENT`.
- **Frontend `data-testid`.** Auth form elements carry stable `data-testid` selectors. Never remove them. Follow the naming scheme: `login-*`, `signup-*`, `verify-*`, `oauth-*`.
- **Window hooks.** `window.__app_ready__`, `window.__auth_snapshot__`, `window.__oauth_complete__`, `window.__TEST_MODE__` are exposed in automation environments only. Guards **must** use `isAutomationEnvironment()` from `@lib/automation` — never `NODE_ENV` checks. `isAutomationEnvironment()` returns `true` for `NEXT_PUBLIC_ENVIRONMENT=local|development|test` and `false` for `staging|production`. Do not remove these hooks. Do not gate them on feature flags.
- **OAuth completion contract.** `window.__oauth_complete__` follows a strict per-attempt lifecycle: `null` (pending, reset at the top of every `startOauthPopup` call) → `"success"` (provider confirmed) or `"failed"` (any non-success terminal: provider error, timeout, popup blocked, navigation failure, user cancel). A `CustomEvent("__oauth_complete__", { detail: { status } })` is dispatched on every terminal transition. Never leave the state as `null` after an attempt resolves.

Important constraints:
- Prefer correctness and maintainability over speed
- Reuse existing abstractions where sensible
- Avoid introducing duplicate layout systems
- Keep implementation scalable for future dashboard sections
- Avoid hardcoded breadcrumbs where possible
- Desktop-first implementation for now
- Do not generate code until investigation is complete
- Be explicit about tradeoffs and uncertainties
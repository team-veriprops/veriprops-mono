# CLAUDE.md

Veriprops is a property verification platform. Monorepo with two deployable apps that talk over HTTP:

- [backend/](backend/) — FastAPI service (Python 3.12, PostgreSQL, async SQLAlchemy, Alembic). See [backend/CLAUDE.md](backend/CLAUDE.md).
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
- **Env & secrets.** Committed `.env.{env}` files (backend `test|dev|staging|prod`, frontend `.env|.env.test|.env.production` plus the deploy-time `.env.dev|.env.staging` bases — Next.js can't auto-load custom names) are **config-only**. `backend/.env.dev_personal` is the one exception — it's gitignored, per-developer, and not part of this committed set; copy `backend/.env.example` to `backend/.env.dev_personal` locally, or skip it entirely and rely on Doppler (both `python veriprops.py` and `docker compose up backend` tolerate it being absent). Secrets live in Doppler (per-app projects `veriprops-backend`/`veriprops-frontend`, configs `prd|stg|dev`) and are injected as process env vars, which pydantic-settings/Next.js give precedence over env files — locally via `doppler run -- …`, in deploys by `deploy.yml` itself: `.github/scripts/doppler_env_args.sh` overlays the Doppler config onto the committed env-file base (Doppler wins per key) and passes the merged set as `--env`/`--build-env` flags to `vercel deploy` (there is **no Doppler→Vercel sync** and no dashboard env vars). The backend env selector `APPODUS_ACTIVE_ENV` also lives in each backend Doppler config. The credential key set is `Settings.SECRET_ENV_KEYS`; committed files keep those keys absent/empty/`CHANGE_ME`, enforced by `backend/test/unit/app/config/test_env_hygiene.py` (which also scans `frontend/.env*` and fails on provider-token-shaped values anywhere).
- **Security invariants.** Traffic is Cloudflare-proxied; the **edge-auth contract** closes the direct-origin bypass (`*.vercel.app` URLs): a Cloudflare Transform Rule injects `x-edge-auth: <EDGE_AUTH_SECRET>`, enforced by the backend `EdgeAuthMiddleware` and the frontend `proxy.ts` check — unset secret ⇒ open (local/test/e2e), so never require it unconditionally. Prod/staging refuse to boot with a placeholder/leaked JWT key. All tokens/OTPs use `secrets` (never `uuid7`/`random`); persisted KV data is text, never `pickle`. Identity/authorization is server-derived, never client-claimed (chat `sender_kind`, admin sub-role grants). Client-bound list DTOs inherit `PageRequest` (pagination only) — the `where`/`order_by`/`query_fields` controls on `InternalPageRequest` are server-only. Post-auth redirects are validated same-origin. See "Security invariants" in [backend/CLAUDE.md](backend/CLAUDE.md) and [frontend/CLAUDE.md](frontend/CLAUDE.md).
- **Path handling.** Use `path.join` / `pathlib` / POSIX-safe APIs — never hardcode `\` or `/` separators.
- **Real-time channel**: **SSE everywhere** (§4.9) — live dashboards, notifications, chat receive, metrics, audit feed. Chat is **admin-mediated + fraud-scanned** so there is deliberately no WebSocket/presence layer; message *sends* are ordinary HTTP POST. Two emitters: verification-keyed (`app/core/realtime/emitter.py`) and per-user (`user_emitter.py`).
- **WhatsApp channel (§7).** A second thin surface over the same backend, not a second backend. Inbound terminates at a signature-verified Meta webhook and joins the **existing** conversation pipeline, so it runs the same fraud scan and lands in the same admin console (Decision K) — never a parallel path. Money, documents, and reports stay on the website: chat hands off via **single-use RS256 links** (`/wa/{pay,upload,report}/[token]`, §7.5) that authorize one action on one case and are not sessions. Transport is chosen by `WHATSAPP_PROVIDER` (below). Business-initiated messages go out as **Meta-approved §7.7 templates**, whose definitions are code-owned and whose approval status is synced from Meta into an admin registry (D59) — Meta accepts free text only inside its 24-hour service window. An agent's reply typed in the console fans back out over the same transport: free text inside that window, and outside it the `window_reopen` template while the agent's own words stay queued until the customer's next message reopens the window (D72). Backend detail in [backend/CLAUDE.md](backend/CLAUDE.md); landings + widget in [frontend/CLAUDE.md](frontend/CLAUDE.md).
- **Event bus (§4.8).** Every domain event is published **once** through the in-process bus (`app/core/events/`); subscribers fan out (SSE re-emit, in-app/email/SMS notifications via a declarative rule table, chat counter). Don't call the SSE emitter or an email sender directly from a service — `await publish_domain_event(DomainEvent(...))` and let the subscribers decide surfacing. See [backend/CLAUDE.md](backend/CLAUDE.md).

## Pagination Convention
Every list that can grow, should be implemented a page as follows:
1. **Backend** -  The API must accept page (zero index) and page_size params, defaulted to 0 and 10 respectively. The API should also return an Object of Page[T], implemented in the file `backend\main\appodus_utils\db\models.py`. The GenericRepo returns this Object through get_page
2. **Frontend** - The frontend receives the value as an Object of Page<T>, implemented in the file `frontend\src\types\models.ts`. It must also implement paginated rendering of the values. For main Table in the Admin pages, use our existing DataTable implemented here `frontend\src\components\ui\table\DataTable.tsx`. The DataTable is fully controlled and server-driven: consumers own `{ page, query, orderBy, ...filters }` and forward all of them to the backend list endpoint (which accepts `page`/`page_size`/`query`) — search, filtering, and pagination are all server-side, never client-only. Any `page.tsx` hosting a DataTable must wrap its client component in `<Suspense>` (Next 16 `useSearchParams` requirement). See [frontend/CLAUDE.md](frontend/CLAUDE.md) for the full pattern.

## CI/CD (GitHub Actions)

Workflows live in [.github/workflows/](.github/workflows/) — never under `backend/.github/` (GitHub ignores nested locations):

- `pull_requests.yml` — the **single PR gate** and the only workflow with a `pull_request:` trigger (PRs to master/dev/staging). It calls backend CI + frontend CI + e2e via `workflow_call` (e2e path-gated to code changes) and aggregates them in a `summary` job; branch protection must require only `Pull Requests / summary` (always reports; any other check can be path-skipped and would block merging forever).
- `backend-ci.yml` / `frontend-ci.yml` — reusable-only quality gates (`workflow_call` from `pull_requests.yml` and `deploy.yml`; **no direct `pull_request:`/`push:` trigger** — either double-runs CI). Jobs are path-filtered via a `changes` job on PRs and always run on pushes.
- `e2e.yml` — full-stack drive-through, reusable-only plus nightly + manual (called by `pull_requests.yml` as a blocking PR gate and by `deploy.yml` as the release gate). Mailpit runs as a named `docker run` container (not a GHA service) so the `messaging_retry` stage can stop/start it.
- `deploy.yml` — branch-driven, one path per environment: push master→Vercel production, push staging→preview + staging alias (the human-QA environment), push dev→preview + dev alias. Every push runs backend CI + frontend CI + **e2e** before deploying (~30–40 min gate, by design). **Database migrations run here** (`doppler run -- alembic upgrade head` under the environment-scoped `DOPPLER_TOKEN_BACKEND` service token, before the backend deploy; frontend deploys after backend) — not in Vercel's buildCommand, so only promoted releases move schema, serialized by the deploy concurrency group. The Doppler token is required because alembic imports `Settings`, whose prod/staging validators demand the real secret set; `DOPPLER_TOKEN_FRONTEND` feeds the frontend deploy's env flags the same way. Both `vercel.json` files pin `git.deploymentEnabled=false`: this pipeline is the **only** deploy path (an out-of-band Vercel deploy would skip migrations — don't re-enable it).

Backend lint/type gates: `ruff check .` and `mypy main` from `backend/`, configured by [backend/ruff.toml](backend/ruff.toml) and [backend/mypy.ini](backend/mypy.ini) — a deliberately lenient day-one baseline (SQLAlchemy classic `Column` models force several mypy codes off; `== None`/`== False` are valid SQL expressions, so E711/E712 stay off). Ratchet stricter over time; never ship a `continue-on-error` check. `ruff`/`mypy` install via `test-requirements.txt`; CI installs `-r requirements.txt -r test-requirements.txt` together (the latter does not include the former). **Deliberately not `backend/pyproject.toml`**: Vercel's Python builder auto-detects any `pyproject.toml` as a dependency manifest and runs `uv lock` against it, which fails without a `[project]` table — this repo's dependencies stay in `requirements.txt` only, so lint/type config lives in tool-native files instead.

## Workflow

When adding a feature/refactoring the codebase, write a short plan and confirm with the user before coding, write tests first, then implement. Update the relevant `CLAUDE.md` if a new pattern emerges that future agents would otherwise have to re-derive.

### Non-negotiable rule
1. No Frontend/Backend duplicate implementations. 
2. As much as possible, deliver all implementation as full vertical slices (backend domains + Alembic migrations + tests + frontend ) so each phase ships demoably end-to-end.
3. For any change/refactor, make sure to also refactor the whole codebase, including all their references and related implementations; no feature should be ophaned.
4. After each code change, refactor all existing tests, run the tests, and fix defects. Also confirm the app builds and lints.
5. Backend is the only source of truth; No facts should be derived on the frontend, delegate such tasks to the backend.
6. When investigating the app ui, use playwright-cli skills.
7. Document the codebase using: variable/class names, comments and docstrings; comments should focus on the use cases, and not on the history, etc.

## Automation determinism

The codebase ships a deterministic foundation for autonomous QA (Playwright + Claude Code). These rules are permanent — do not remove them:

- **OTP_MODE contract.** `OTP_MODE=deterministic` means all OTP calls return `TEST_OTP` (654123). `OTP_MODE=random` generates real random codes. `ENVIRONMENT=test` requires `deterministic`. `ENVIRONMENT=prod` requires `random`. Startup fails otherwise. Never compare `ENVIRONMENT` string to detect OTP behaviour — always read `OTP_MODE`.
- **WHATSAPP_PROVIDER contract.** `WHATSAPP_PROVIDER=stub` records outbound messages in an in-process outbox and accepts injected inbound ones (`POST /dev/whatsapp/inbound`, `GET /dev/whatsapp/outbox`); `meta` is the live Cloud API. `ENVIRONMENT=test` requires `stub` — **CI and e2e never reach Meta** — and `ENVIRONMENT=prod` requires `meta`. Startup fails otherwise. The two transports are exclusive with no fallback between them, so a live-send failure can never be silently absorbed by the stub. Never detect transport behaviour from `ENVIRONMENT` — read `WHATSAPP_PROVIDER`. The same switch selects the **template directory** (`providers/whatsapp/directory.py`), which reads §7.7 approval status back from Meta: the stub reports the declared set as approved so the channel stays demoable, and no automated run ever calls the Graph API.
- **Dev endpoints.** `POST /dev/reset` and `POST /dev/seed` are available in all non-production environments. They are production-gated twice: the router only mounts in non-prod, and `_require_non_prod()` returns 404 in production. Never remove these guards.
- **Mailpit SMTP.** In dev/local/test environments, email is captured by Mailpit (SMTP on `localhost:1025`). The `SmtpEmailProvider` hard-fails in production and staging. Do not add `EMAIL_PROVIDER` settings — the router selects SMTP automatically based on `ENVIRONMENT`.
- **Frontend `data-testid`.** Auth form elements carry stable `data-testid` selectors. Never remove them. Follow the naming scheme: `login-*`, `signup-*`, `verify-*`, `oauth-*`.
- **Window hooks.** `window.__app_ready__`, `window.__auth_snapshot__`, `window.__oauth_complete__`, `window.__TEST_MODE__` are exposed in automation environments only. Guards **must** use `isAutomationEnvironment()` from `@lib/automation` — never `NODE_ENV` checks. `isAutomationEnvironment()` returns `true` for `NEXT_PUBLIC_ENVIRONMENT=dev_personal|development|test` and `false` for `staging|production`. Do not remove these hooks. Do not gate them on feature flags.
- **OAuth completion contract.** `window.__oauth_complete__` follows a strict per-attempt lifecycle: `null` (pending, reset at the top of every `startOauthPopup` call) → `"success"` (provider confirmed) or `"failed"` (any non-success terminal: provider error, timeout, popup blocked, navigation failure, user cancel). A `CustomEvent("__oauth_complete__", { detail: { status } })` is dispatched on every terminal transition. Never leave the state as `null` after an attempt resolves.

Important constraints:
- Prefer correctness and maintainability over speed
- Abstract every function, class, component, etc, that are related and used in 2+ surfaces/places.
- Reuse existing abstractions where sensible
- Avoid introducing duplicate layout systems
- Keep implementation scalable for future upgrades, e.g: backend and frontend
- Avoid hardcoded breadcrumbs/Routes where possible
- **Enum references, never free literals.** Any value that has a defining enum (statuses, tiers, roles, channels, currencies, event types, permissions, …) must be referenced via its enum member in app code — in comparisons, dict/set keys & values, defaults, and DTOs. Free string literals duplicating an enum value are prohibited. Exceptions: enum *definitions* themselves, Alembic migrations (kept decoupled from app enums by design — raw strings / numeric `server_default`s), and tests deliberately asserting wire/DB-string compatibility.
- Mobile-first, highly responsive implementation
- Do not generate code until investigation is complete
- Be explicit about tradeoffs and uncertainties
- Always ask me questions when you lack clarity.
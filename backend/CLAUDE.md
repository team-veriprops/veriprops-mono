# CLAUDE.md

FastAPI service for Veriprops. Async SQLAlchemy, Alembic migrations, Kink DI, PostgreSQL.

## Commands

```bash
pip install -r requirements.txt

# Active env selects which .env.{name} file is loaded at import time.
# Valid names: local, test, dev, staging, prod.
export appodus_active_env=local        # bash
$env:appodus_active_env="local"        # PowerShell
set appodus_active_env=local           # cmd

python veriprops.py                    # dev server, http://localhost:8000 (docs at /docs)

# Tests — pytest auto-loads conftest.py which defaults appodus_active_env=test.
# Force the test env explicitly when running migrations against the test DB.
set appodus_active_env=test && alembic upgrade head && pytest
pytest test/unit/app/path/to/test_file.py::test_name   # single test

# Alembic
alembic upgrade head                                          # apply
alembic downgrade -1                                          # roll back one
alembic revision --autogenerate -m "describe change"          # generate
```

`appodus_active_env` is read at module import (see [conftest.py](conftest.py) and [appodus_utils/config/settings.py](main/appodus_utils/config/settings.py) `set_env_vars()`). It must be set before any `main.*` import — that's why `conftest.py` defaults it before importing settings.

## Architecture

### Two-layer Python package

- [main/app/](main/app/) — Veriprops-specific business code (domains, settings, seeder, jobs).
- [main/appodus_utils/](main/appodus_utils/) — reusable framework/library code (DI bootstrap, generic repo, transactional decorator, integrations, middleware, exceptions). Treat as a vendored library: prefer extending via subclass over editing in place. App-side `DiBootstrap` in [main/app/config/bootstrap.py](main/app/config/bootstrap.py) subclasses `BaseDiBootstrap` to inject app-specific deps (Redis).

### Domain module shape

Each domain must live in its **own package** and encapsulate all domain concerns. Related child domains must be **grouped and contained within their parent domain package**.

| File            | Responsibility                                                                           |
| --------------- | ---------------------------------------------------------------------------------------- |
| `models.py`     | SQLAlchemy ORM model + Pydantic DTOs (`CreateDto`, `UpdateDto`, `QueryDto`, `SearchDto`) |
| `repo.py`       | Data access layer — extends `GenericRepo`, should never call the session object directly                                                |
| `service.py`    | Business logic — service methods decorated with `@transactional`                         |
| `controller.py` | FastAPI router (only when the domain exposes HTTP endpoints)                             |
| `validator.py`  | Input validation + business-rule validation                                              |

### Domain registration convention

New domains must be wired into the **domain package hierarchy**.

* Every domain package must be **imported and exposed by its parent domain package**.
* Root parent domains must be imported and exposed in `main/app/domain/__init__.py`.
* `main.app.domain` is the **single aggregation point** imported by Alembic, so every domain must be reachable through this package hierarchy for autogenerate to discover all models. Domains that has `controller.py`, don't need to register it's models directly; this would be picked from the controller.
* A domain is defined as a single unit comprizing of models.py, optional repo.py, service.py, validator.py, optional controller.py, etc; bounded by a single entity that extends BaseEntity. No more than a single entity should be found in a domain. The codebase should be properly packaged using this pattern.  

### Routing convention

* Domains that expose HTTP endpoints should define a `controller.py` router.
* Child domain routers must be mounted in their **parent domain router**.
* Root parent domain routers must be mounted in `main/app/domain/__init__.py`.
* Domains without HTTP endpoints do **not** need a router, but must still be wired into the package hierarchy. However, domains with router mounted in their parent domain router don't need any further wiring.

### Non-negotiable rule

A domain is **not considered complete** until:

* its package is created.
* it is exposed through the parent domain package hierarchy,
* and, where applicable, its router is mounted in the appropriate parent router (or root router in `main/app/domain/__init__.py`); but not both.


### Database/ DB migration conventions:

* SQLAlchemy + Alembic
* No database foreign keys
* No cascade constraints
* No ON DELETE / ON UPDATE constraints
* Use application-enforced references
* Reference IDs are normal indexed columns
* Alembic migrations must never emit ALTER TABLE ... ADD FOREIGN KEY
* Don't create duplicate indexes, prefer UniqueConstraint to create_index. Declare a column's index **once** — either inline (`Column(..., index=True)`, which auto-names `ix_<table>_<col>`) or in `__table_args__`, never both. If you use `__table_args__`, the `Index(name, ...)` name must match the migration's `create_index` name exactly (a mismatch produces two indexes on autogenerate).
* When mapping date/datetime, don't use DateTime or TIMESTAMP directly, instead use UTCDateTime in the file `backend/main/appodus_utils/db/models.py`
* **JSON columns.** Plain JSON columns use the shared `JSONB_VARIANT` singleton (`Column(JSONB_VARIANT)`) — renders as JSONB on Postgres, JSON elsewhere. **Mutable JSON columns must use a fresh `jsonb_variant()` instance per column** — `Column(MutableDict.as_mutable(jsonb_variant()))`, `Column(MutableList.as_mutable(jsonb_variant()))`. Never pass the shared `JSONB_VARIANT` singleton to `as_mutable(...)`: `Mutable.as_mutable` installs a process-global listener that binds its coercion to every column whose type *is that same instance* (identity match), so reusing one instance leaks (e.g.) `MutableList` coercion onto unrelated dict columns and a `dict` assignment then raises `Attribute 'x' does not accept objects of type <class 'dict'>`. Both `JSONB_VARIANT` and `jsonb_variant()` live in `appodus_utils/db/models.py`; the type instance is irrelevant to generated DDL, so migrations keep using `JSONB_VARIANT`.
* Always use the pattern implemented in alembic migrations here `backend\main\alembic\versions\0001_initial_schema.py`, including the use separate utility methods for each migration and the use of utility methods, and DRY principle.
* **Every entity needs a builder — the orphan guard.** Each new `BaseEntity` subclass must get a `_create_<table>()` helper **and** be registered in `_TABLE_BUILDERS`. Forgetting the registration produces a mapped model whose table `alembic upgrade head` never creates — every query then 500s. `test/unit/app/test_migration_schema_parity.py` fails CI on any drift between `BaseEntity.metadata.tables` and `_TABLE_BUILDERS` (in both directions), so it catches the omission before runtime. This applies to framework/vendored entities too (e.g. `devices`, `callbacks`), which live outside `domain/**` but are still reachable through the import graph.



### Enum & status conventions

**Enum references, never free literals.** Any value that has a defining enum — verification/task/report state (`main/app/core/state/status.py`), tiers, agent roles, `UserType`, `SecurityEventType`, `MessageStatus`/`MessageChannel`, `TransactionCurrency`, `IdempotencyStatus`, `Permission`, etc. — must be referenced via its enum member in app code (services, repos, validators, controllers, models/DTOs, state tables). This applies to comparisons, dict/set keys & values, defaults, and `server`-side logic.

* Canonical lifecycle enums live in `main/app/core/state/status.py`; the state tables in `main/app/core/state/machine.py` reference those members (annotated `Dict[str, Set[str]]` since the enums subclass `str`, so `StateMachine` still accepts DB strings at the boundary).
* **Exceptions:** enum *definitions* themselves (`DRAFT = "DRAFT"`); **Alembic migrations**, which stay decoupled from app enums by design (raw strings / numeric `server_default`s); and tests deliberately asserting wire/DB-string compatibility.

### Generic repository

`GenericRepo[Model, Create, Update, Query, Search]` ([appodus_utils/db/repo.py](main/appodus_utils/db/repo.py)) provides CRUD, pagination, and soft-delete-aware queries. Entities inherit from `BaseEntity` which adds `id` (UUID), `date_created`, `date_updated`, `version` (optimistic locking), `deleted` (soft-delete flag) — never `DELETE` rows by hand; flip `deleted`. Pagination is zero indexed (First page = 0)

- **`version` is the optimistic-lock counter — never reuse it for domain versioning.** A versioned entity needs its own purpose-named column (e.g. `consent_version` on `ConsentDocument`).
- **`update()` runs the DTO through `jsonable_encoder`**, which turns `datetime`/enum values into strings before binding. Don't push `datetime` fields through the update path (asyncpg rejects a string for a timestamp column) — set those on `create()` instead and keep `Update*Dto` to editable text/scalar fields.
- **ID formats — the two-string-forms gotcha.** `BaseEntity.id` is a native `UUID(as_uuid=True)`, so `entity.id` is a `uuid.UUID`. Reference columns are `String(36)`, and two string forms are in play: **entity ids travel as `.hex` (32-char)** — the `Object` base coerces a `UUID` id field to `.hex`, so that is what DTOs return and the frontend echoes back — while **user ids are `str(uuid)` (36-char)** because the JWT subject is `str(user.id)`. When you use a *freshly-created or fetched* entity's `.id` as a reference (or query a `String` ref column), coerce it: `Utils.uuid_to_hex(entity_id)` for entity refs (conversation/verification/property/…), `str(user_id)` for user refs. Passing a raw `uuid.UUID` to a `String` column makes asyncpg raise `expected str, got UUID`; passing `str(uuid)` (36-char) where the wire uses `.hex` (32-char) silently mismatches. PK lookups (`get_model`) accept any form via `_ensure_uuid`.
- **`build_page` validates its items as DTOs — never hand it ORM models.** For a custom paged query, return `(rows, total)` from the repo and build the page in the service from DTOs (`self._repo._db_utils.build_page(dtos, total, page, page_size)`). The stock `get_page` already passes DTOs; a hand-written repo method that passes ORM models fails Pydantic validation at response time.
- **Don't re-fetch a row you created in the same (uncommitted) transaction.** `get_model(new.id)` right after `create_return_model(...)` can return `None`. Set fields on the returned attached object and return it directly (e.g. `ReportService.release`).

### Transaction management

`@transactional(session_policy=...)` ([appodus_utils/decorators/transactional.py](main/appodus_utils/decorators/transactional.py)) wraps async functions:

- `USE_IF_PRESENT` (default) — joins the request's session set by `DBSessionMiddleware`. Raises if no session is in context.
- `ALWAYS_NEW` — opens an isolated session/transaction (use for jobs/seeders running outside a request).
- `FALLBACK_NEW` — joins context if present, else opens new.

Inside a transactional service method, get the session via `get_db_session_from_context()` — don't accept a session parameter.

### Dependency injection (Kink)

Bootstrap runs once at import: importing settings → importing bootstrap → registers `logger`, `Redis`, `AuthJWTBearer`, `AsyncClient` in `di`. Services/repos resolve via `di[T]`. New cross-cutting deps go into a `DiBootstrap` override, not into module-level globals.

**Name injected dependencies after their type, not their role.** A constructor param and the attribute it feeds must both name the concrete dependency: `def __init__(self, property_repo: PropertyRepo): self._property_repo = property_repo` — never the generic `self._repo = property_repo` or `self._repo = repo`. Kink autowires by type hint, so the param name is free to be descriptive. This keeps every reference site self-documenting when a service holds several repos/collaborators.

### Request lifecycle

[veriprops.py](veriprops.py) wires the FastAPI app:

- `DBSessionMiddleware` — opens an async session per request, stores it in a `ContextVar` so `@transactional` can find it.
- `RequestLoggingMiddleware` — request/response logs.
- Exception handlers map `AppodusBaseException` and friends to structured HTTP responses (`exception/exception_handlers.py`). All custom exceptions inherit from `AppodusBaseException` and carry context (`user_id`, `resource`, etc.) — raise these, don't `raise HTTPException` directly.
- Lifespan: `ClientStateManager` opens external clients (HTTPX, Redis), then `DataSeeder.run_data_seed()` seeds reference data.

Routes mount under `/api`. Webhooks mount under `WEBHOOK_PATH` (default `/webhooks`) via `webhook_router`.

### Serverless-aware DB engine

[appodus_utils/db/session.py](main/appodus_utils/db/session.py) picks `NullPool` when `DEPLOYMENT_IS_SERVERLESS=true` (Vercel) and a real pool otherwise. Don't cache engines or sessions across requests in serverless.

## Settings

`Settings` ([main/app/config/settings.py](main/app/config/settings.py)) extends `AppodusBaseSettings` and is loaded from `.env.{appodus_active_env}` at import. Notable knobs:

- `ACTIVE_DB`, `SQLALCHEMY_DATABASE_URI` — DB selection (PostgreSQL via `asyncpg`; `settings.SupportedDB` still supports other dialects).
- `ACTIVE_PAYMENT_METHOD` — `FLUTTERWAVE` or `PAYSTACK`.
- `ALLOWED_ORIGINS` — comma-separated CORS origins.
- `ENABLE_OUT_MESSAGING`, `ALLOW_AUTH_BYPASS`, `DISABLE_RATE_LIMITING` — gate side effects in non-prod.
- `GOOGLE_SERVICE_ACCOUNT_FILE` — path resolved via `get_absolute_path` (walks up out of `test/`, `main/`, or `appodus_utils/`).
- `PHONE_VERIFICATION_ENABLED` — toggles the phone-verification step in the email/OAuth signup flow. When `false`, signup collects the number but stores `phone_verified=False`; phone is then verified at the payment step (PRD §10.5). `AuthService.signup`/`complete_profile` read it; the frontend reads it via `/config/public`.

**Where a knob lives — two config layers.** Infra / deploy / security operational knobs (timeouts, TTLs, hosts, SSE heartbeat/queue, OTP resend caps, draft lifetimes, page-batch sizes) are `Settings` fields with sensible in-code defaults, overridable via `.env.{env}`; [.env.example](.env.example) is the committed, secret-free template of every settable key. **Admin-tunable business rules** that must change at runtime without a redeploy (SLA-at-risk horizon, payout SLA, dispute min-length, share-link expiry, analytics trend window — the full table is PRD §R.2) live in the `system_config` `ConfigKey` store — read via `self._config.get_int(ConfigKey.X)`, seeded idempotently by `DataSeeder`. **No shadowing constants:** never re-declare a module-level literal that duplicates an existing setting/ConfigKey (a prior `_PRICE_LOCK_HOURS`/`INVITE_TTL_HOURS` silently ignored the setting). Selector/mode values are enum-typed (`OtpMode`, `PricingFxProvider`, `ReviewDecision`); `GEOCODING_PROVIDER`/`KYC_PROVIDER` stay `str` because their enums live in the `integrations` package, which imports the `settings` singleton back (a cycle) — the provider factories coerce at their boundary (`GeoProvider(settings.GEOCODING_PROVIDER)`).

### Reference content & public config

- **Legal documents are backend-owned.** Prose lives in the content registry at `app/domain/user/auth/consent/content/`, is upserted idempotently by `DataSeeder.run_data_seed` → `ConsentService.seed_documents` (keyed on `(type, consent_version)`), and is served publicly by `GET /users/auth/consents/documents[/{slug}]`. Edit the registry, not the migration — the `0001` rows are metadata only; bodies/sign-off land at seed time. `ConsentSignoffStatus` marks DRAFT vs FINAL wording.
- **Public runtime flags** the frontend needs go through `app/domain/config` → `GET /config/public` (`PublicConfigDto`). Backend stays the source of truth; don't duplicate flags as frontend env vars.
- **Cross-portal counts** (`app/domain/user/auth/cross_portal`): `CrossPortalService` keeps a registry of per-persona count sources. It returns 0 per persona until later slices call `register_source(...)`; the `/users/auth/cross-portal/summary` endpoint feeds the frontend's portal badge.
- **Session revocation is enforced on refresh:** `POST /users/auth/sessions/current` rejects a refresh whose `device_sessions` row is revoked/absent, so device-revoke and reset-time revoke-all actually end sessions. Read the refresh cookie via `settings.AUTHJWT_REFRESH_COOKIE_KEY` (`__Host-refresh_token`) — never the bare literal `"refresh_token"`, or the lookup silently misses and revocation breaks.

## Security invariants (do not regress)

These are permanent guardrails from the secure-coding audit. Keep them intact:

- **Secrets live in `.env.{env}` (git-ignored), never as committed defaults.** Committed source uses the `SECRET_PLACEHOLDER` sentinel (`appodus_utils/config/settings.py`). The `AUTHJWT_SECRET_KEY` env-var name must match the settings field **exactly** (a prior `JWT_SECRET_KEY` typo silently fell back to a committed default). `_enforce_prod_secret_policy` **fails startup** in prod/staging when `AUTHJWT_SECRET_KEY`/`APPODUS_CLIENT_SECRET` is a placeholder/leaked-default or `ALLOW_AUTH_BYPASS` is true — never weaken it. JWT alg is pinned to HS256 (`AUTHJWT_ALGORITHM`/`AUTHJWT_DECODE_ALGORITHMS`); don't leave it unset.
- **CSPRNG for all tokens.** `Utils.random_str` (alphanumeric) and random-mode OTP use `secrets`, never `uuid7`/`random`. Any new token/code/reference must go through `Utils.random_str` or `secrets` directly.
- **No pickle for persisted data.** `KeyValueService` stores UTF-8 text and returns decoded strings (mirroring `RedisUtils.get_redis`). Never reintroduce `pickle` on DB/Redis values.
- **`PageRequest` vs `InternalPageRequest` ([db/models.py](main/appodus_utils/db/models.py)).** `PageRequest` (client-safe: `page`/`page_size`) is the only base a wire-bound request DTO may inherit. The flexible query controls (`where`/`order_by`/`query_fields`/`exact_string_values`) live on `InternalPageRequest` and are **server-set only** — a `Search*Dto` bound from the wire must never expose them (they can filter/sort on any column). `DbUtils`/`GenericRepo` read the controls via `getattr(..., default)` so both bases work.
- **Ownership is enforced in the service/repo layer, not auto-scoped.** `build_search_criterion` does not add a tenant filter — every service that returns another user's data must gate on the caller's id (see `VerificationService.get_owned`, `PayoutService._get_owned`). Never expose an unauthenticated list endpoint that binds a `Search*Dto`.
- **Server-derived identity, never client-claimed.** Chat `sender_kind` is derived from the caller's role + thread type in `CommunicationService.post_message` — never accepted from the request. Admin sub-role changes (`admin_team`) are `INVITE_ADMIN`-gated (SUPER-only), forbid self-targeting, and only a SUPER may grant SUPER.
- **Edge rate limiting.** Sensitive unauthenticated routes (login, `otp/send`, `otp/verify`, `password/forgot`, `password/reset`, `signup`) use the reusable `RateLimiter` dependency ([appodus_utils/common/rate_limit.py](main/appodus_utils/common/rate_limit.py)), which is disabled wholesale by `DISABLE_RATE_LIMITING`. Add it to any new sensitive unauthenticated endpoint.
- **Webhooks & logging.** Webhook signatures verify with `hmac.compare_digest` and fail closed on a missing/placeholder secret. Never log full webhook bodies or headers (PII + provider signatures) — log metadata only. `DB_ENABLE_LOGS` defaults `False` (SQL echo leaks bound params); keep it off in prod. The full settings snapshot is held in-process (`get_full_settings_json()`), never dumped to `os.environ`.

## Integrations

Provider-agnostic interfaces in [appodus_utils/integrations/](main/appodus_utils/integrations/) — pick implementation via settings:

| Purpose | Providers |
|---|---|
| File storage | AWS S3 (`veriprops-documents`), R2 |
| Document signing | Zoho DocSign (webhook in `domain/webhook/`) |
| File collaboration | Google Drive (service-account auth) |
| Payments | Flutterwave, Paystack |
| Email | SendGrid, Mailjet |
| SMS | Twilio, Termii |
| WhatsApp | Meta Business API |
| Push | Firebase, Web Push |

Webhook receivers live under `appodus_utils/integrations/.../webhook.py` and are mounted via the shared `webhook_router`.

### Messaging & templating pattern

All external channel dispatch (email, SMS, push, WhatsApp) goes through the messaging integration at `appodus_utils/integrations/messaging/`.

**To send a new notification type — follow all four steps in order:**

1. **Register the template slug** in `appodus_utils/integrations/messaging/templating/models.py` → `AvailableTemplate` enum.
   ```python
   MY_NEW_EVENT = "my_new_event"  # Email, SMS
   ```

2. **Add context variables** for any dynamic data in `appodus_utils/integrations/messaging/models.py` → `MessageContext` enum.
   ```python
   MY_EVENT_SOME_FIELD = "MY_EVENT_SOME_FIELD"  # my_new_event — description
   ```
   Global variables (`FIRST_NAME`, `BRAND`, `BRAND_SUPPORT_EMAIL`, etc.) are injected automatically via `MessageContextModule.USER` and don't need entries.

3. **Create Jinja2 template files** for each channel the notification supports, named exactly `{AvailableTemplate.slug}.jinja2`:
   - `appodus_utils/integrations/messaging/templates/email/my_new_event.jinja2`
   - `appodus_utils/integrations/messaging/templates/sms/my_new_event.jinja2` (if SMS)
   - `appodus_utils/integrations/messaging/templates/push/my_new_event.jinja2` (if push)
   - etc.

   Template variables use **UPPERCASE** matching the `MessageContext` enum values. The first line of email templates must be `Subject: ...`.

4. **Add a send method** to the domain's message class (a subclass of `BaseMessageSender` in `app/domain/message/`):
   ```python
   async def send_my_event(self, recipient_user_id: str, some_field: str) -> None:
       await self._send_message(
           recipient_user_id=MessageRecipientUserId(user_id=recipient_user_id),
           template=AvailableTemplate.MY_NEW_EVENT,
           context_modules=[MessageContextModule.USER],
           category=MessageCategory.TRANSACTION,
           default_channels=[MessageChannel.EMAIL],
           extra_context={MessageContext.MY_EVENT_SOME_FIELD.value: some_field},
       )
   ```

**Non-negotiable:** Every `AvailableTemplate` entry must have a matching template file for every channel it declares. Registering the enum entry without the template file will cause a runtime error when the notification fires.

### Message bookkeeping & delivery retries

Every dispatch is recorded in the single `messages` table (there is **no separate DLQ entity** — one lifecycle, one source of truth). `MessagingService.send_message` persists the row **before** dispatch and adopts the generated id onto the in-flight DTO; outcomes: `SENT` (with `sent_at`/`provider`), `RETRYING` (transient failure, `next_retry_at` scheduled), `FAILED` (permanent). `MessageService` bookkeeping is `ALWAYS_NEW`-transactional on purpose: the row records an external side effect that already happened, so it must commit independently of the caller's transaction (and it keeps concurrent `send_bulk` branches off the shared request session).

- **Retry sweep.** `MessagingService.process_retries` re-dispatches `RETRYING` rows whose `next_retry_at` passed, via `MessageRouter` (fresh provider selection/circuits). Runs on APScheduler every minute (`message_retry_check` in `app/jobs/scheduled.py`) + on demand via admin `POST /messages/sweeps/retries` (CONFIGURE_SYSTEM).
- **Backoff & threshold.** `MESSAGING_RETRY_INTERVALS_SECONDS` (Settings, default `[60, 300, 900]`, env override is a JSON list) is the backoff ladder; the retry threshold is its length — after that many failed retries the row goes permanently `FAILED`. Validation/rate-limit errors never retry.
- **Time-bound content (`expires_at`).** OTPs and reset links are useless (or stale — resends overwrite the KV code) past their validity, so their senders stamp `expires_at` (OTP: `now + OTP_CODE_TTL_SECONDS`; reset: `now + PASSWORD_RESET_TTL_SECONDS`). The pipeline never dispatches or schedules a retry past `expires_at` — expired rows fail permanently with an "expired before delivery" error. Plumbing mirrors `schedule_at`: sender passes `expires_at=` to `BaseMessageSender._send_message`/`_send_direct_message` → context key → channel builders → `MessageRequest.expires_at` → column. Any new time-bound notification must set it.
- **DTO gotchas.** Pydantic v2 treats `Optional[...]` **without a default** as required — partial-update/search DTOs (`_UpdateMessageDto`, `Search*Dto`) must keep explicit `= None` defaults. `UpsertMessageDto.from_request` maps the request's `schedule_at` → DTO `scheduled_at` explicitly (models ignore extra fields, so a raw dump silently drops it).

### Event bus & notifications (PRD §4.8 / §17)

Every domain event is published **once** on the in-process synchronous bus (`app/core/events/`); subscribers decide surfacing. **Services never call the SSE emitter or an email sender directly** — they publish a `DomainEvent`:

```python
from main.app.core.events import DomainEvent, EventType, publish_domain_event
await publish_domain_event(DomainEvent(
    type=EventType.STATUS_CHANGED,          # None = a pure SSE-refresh nudge (no notification)
    verification_id=vid,                    # scopes the verification-keyed SSE re-emit
    recipient_user_ids=(customer_id,),      # who gets the in-app notification + per-user SSE (str/36-char)
    sse_event=VerificationEventType.STATUS_CHANGED.value,  # preserves the exact S13 SSE event name
    data={"status": new_status.value},
))
```

Publishing is **best-effort per subscriber** (one failure never breaks another or the emitting transaction). The standard subscribers (registered at bootstrap in `app/core/events/subscribers.py`): `realtime` (re-emits the verification + user SSE), `notification` (rule-table fan-out → in-app + email/SMS), `chat_counter` (Chat counter for `MESSAGE_SENT`), `chat_autopost` (SYSTEM breadcrumb into the customer thread on `STATUS_CHANGED`).

**To make an event notify a user:** add an `EventType`, a row in `notification/rules.py` (`in_app`/`email`/`sms`/`chat_only` + the `AvailableTemplate`), copy + link in `notification/content.py`, and publish the event. The rule table covers the full PRD §17.2 trigger set. Time-driven events (e.g. `SlaBreached`) fire from a scheduler sweep (`app/jobs/scheduled.py`, `ALWAYS_NEW`, disabled under test, with an admin dev endpoint).

## Dev/QA endpoints (non-production only)

`POST /dev/reset` + `POST /dev/seed` (`app/domain/dev/`) are the automation-determinism contract: reset clears domain data (keeping the super-admin + reference seeds), seed builds a deterministic scenario (customer + approved agents + an `UNDER_REVIEW`, SLA-overdue verification). `GET /dev/messages/latest?recipient=` (bookkeeping snapshot of the newest outbound message) and `POST /dev/messages/rewind?recipient=&rewind_expiry=` (pulls `next_retry_at`/`expires_at` into the past so the retry sweep fires immediately against the default backoff ladder; touches only those timestamps) extend the same contract for the messaging-retry pipeline. **Production-gated twice** — the router only mounts when `settings.ENVIRONMENT != PRODUCTION`, and `_require_non_prod()` 404s in prod. Never remove either guard. The committed live drive-through `backend/scripts/e2e_drive_through.py` runs one cradle-to-grave scenario over HTTP against a running server — fresh signup (referral code) → agent onboarding/KYC-stub + admin-invitation RBAC → draft/quote/submit → stub payment → assignment/execution (evidence) → chat fraud-hold approve+reject/SLA → review (reject/rework, release gate) → release → report PDF → tracking/SSE → sharing → dispute/re-check/upgrade → payouts → PREMIUM finish (LAWYER task, v2/v3 reports, declined re-check, upheld dispute) → referral earn+spend → pricing/analytics/broadcast hardening → pool/no-show/starvation + pause/delay/cancel/fail + chargeback (on the seeded "ops" verification) → audit pack + erasure reject/execute → Mailpit email delivery + password reset → outbound-message failure→retry→threshold→expiry (`messaging_retry`, last: stops/starts the Mailpit container via the docker CLI to induce a real SMTP failure, drives `POST /messages/sweeps/retries` with `/dev/messages/rewind` for interval-independence). Stages live in `backend/scripts/e2e/` (shared harness in `e2e/harness.py`); `--stages` runs a contiguous prefix of the stage order (stages have linear data dependencies). Best coverage: `docker compose up -d mailpit` and run the backend with `ENABLE_OUT_MESSAGING=True` (email → Mailpit, SMS → mock provider); without Mailpit (or docker CLI) the email + messaging_retry stages warn-skip and the rest still passes.

## Redis
We don't use Redis directly, rather we rely on `RedisUtils` in `backend/main/appodus_utils/db/redis_utils.py`. This uses Redis when available, but fallback to an SQL implementation when not available.

## Tests

- `test/unit/` — fast, in-memory; mirrors `main/app/` structure.
- `test/utils/` — `mock_circuit_breaker.py`, shared fixtures.
- `pytest.ini` sets `asyncio_mode = auto`, so async tests need no decorator.
- `Mailpit` is used for email during tests
- ``
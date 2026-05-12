# CLAUDE.md

FastAPI service for Veriprops. Async SQLAlchemy, Alembic migrations, Kink DI, MySQL.

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
* `main.app.domain` is the **single aggregation point** imported by Alembic, so every domain must be reachable through this package hierarchy for autogenerate to discover all models.

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


### Database conventions:

* SQLAlchemy + Alembic
* No database foreign keys
* No cascade constraints
* No ON DELETE / ON UPDATE constraints
* Use application-enforced references
* Reference IDs are normal indexed columns
* Alembic migrations must never emit ALTER TABLE ... ADD FOREIGN KEY
* Don't create duplicate indexes, prefer UniqueConstraint to create_index.



### Generic repository

`GenericRepo[Model, Create, Update, Query, Search]` ([appodus_utils/db/repo.py](main/appodus_utils/db/repo.py)) provides CRUD, pagination, and soft-delete-aware queries. Entities inherit from `BaseEntity` which adds `id` (UUID), `created_at`, `updated_at`, `version` (optimistic locking), `deleted` (soft-delete flag) — never `DELETE` rows by hand; flip `deleted`.

### Transaction management

`@transactional(session_policy=...)` ([appodus_utils/decorators/transactional.py](main/appodus_utils/decorators/transactional.py)) wraps async functions:

- `USE_IF_PRESENT` (default) — joins the request's session set by `DBSessionMiddleware`. Raises if no session is in context.
- `ALWAYS_NEW` — opens an isolated session/transaction (use for jobs/seeders running outside a request).
- `FALLBACK_NEW` — joins context if present, else opens new.

Inside a transactional service method, get the session via `get_db_session_from_context()` — don't accept a session parameter.

### Dependency injection (Kink)

Bootstrap runs once at import: importing settings → importing bootstrap → registers `logger`, `Redis`, `AuthJWTBearer`, `AsyncClient` in `di`. Services/repos resolve via `di[T]`. New cross-cutting deps go into a `DiBootstrap` override, not into module-level globals.

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

- `ACTIVE_DB`, `SQLALCHEMY_DATABASE_URI` — DB selection (MySQL; async drivers).
- `ACTIVE_PAYMENT_METHOD` — `FLUTTERWAVE` or `PAYSTACK`.
- `ALLOWED_ORIGINS` — comma-separated CORS origins.
- `ENABLE_OUT_MESSAGING`, `ALLOW_AUTH_BYPASS`, `DISABLE_RATE_LIMITING` — gate side effects in non-prod.
- `GOOGLE_SERVICE_ACCOUNT_FILE` — path resolved via `get_absolute_path` (walks up out of `test/`, `main/`, or `appodus_utils/`).

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
           category=MessageCategory.TRANSACTIONAL,
           default_channels=[MessageChannel.EMAIL],
           extra_context={MessageContext.MY_EVENT_SOME_FIELD.value: some_field},
       )
   ```

**Non-negotiable:** Every `AvailableTemplate` entry must have a matching template file for every channel it declares. Registering the enum entry without the template file will cause a runtime error when the notification fires.

## Redis
We don't use Redis directly, rather we rely on `RedisUtils` in `backend/main/appodus_utils/db/redis_utils.py`. This uses Redis when available, but fallback to an SQL implementation when not available.

## Tests

- `test/unit/` — fast, in-memory; mirrors `main/app/` structure.
- `test/utils/` — `mock_circuit_breaker.py`, shared fixtures.
- `pytest.ini` sets `asyncio_mode = auto`, so async tests need no decorator.
- `Mailpit` is used for email during tests
- ``
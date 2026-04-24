# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Set active environment (local | dev | staging | prod)
export appodus_active_env=local

# Run dev server
python veriprops.py

# Database migrations
alembic upgrade head               # Apply all pending migrations
alembic downgrade -1               # Roll back one migration
alembic revision --autogenerate -m "describe change"  # Generate migration
```

Environment config is loaded from `.env.{appodus_active_env}` at startup. FastAPI docs available at `http://localhost:8000/docs`.

---

## Architecture

### Domain-Driven Design

Each business domain lives under `main/app/domain/{entity}/` and follows this structure:

| File | Responsibility |
|---|---|
| `models.py` | SQLAlchemy ORM model + Pydantic DTOs (`CreateDto`, `UpdateDto`, `QueryDto`, `SearchDto`) |
| `repo.py` | Data access — extends `GenericRepo` |
| `service.py` | Business logic — methods decorated with `@transactional` |
| `controller.py` | FastAPI router/routes |
| `validator.py` | Input validation and business rule checks |

New domains must be registered in `domain/__init__.py`.

### Dependency Injection (Kink)

Classes decorated with `@inject` are registered in and resolved from the DI container. Bootstrap runs in `config/bootstrap.py` on startup (initializes logger, DB session, Redis, registers custom types).

```python
@inject
class BankService:
    def __init__(self, bank_repo: BankRepo, bank_validator: BankValidator): ...
```

### Transaction Management

Three session policies available on `@transactional`:

- `USE_IF_PRESENT` — joins existing session (default)
- `ALWAYS_NEW` — isolated new session
- `FALLBACK_NEW` — uses context session if available, otherwise creates one

### Generic Repository

`GenericRepo[Model, Create, Update, Query, Search]` provides CRUD, pagination (`get_page`), and soft-delete-aware queries out of the box. All entities inherit from `BaseEntity` which adds `id` (UUID), `created_at`, `updated_at`, `version` (optimistic locking), and `deleted` (soft delete flag).

### Exception Handling

All exceptions inherit from `AppodusBaseException`. They carry structured context (user_id, resource, email, etc.) and map to HTTP status codes via handlers in `exception/exception_handlers.py`.

### Key Middleware

- `DBSessionMiddleware` — per-request async SQLAlchemy session
- `RequestLoggingMiddleware` — logs all requests/responses
- `CORSMiddleware` — allowed origins from settings

### Data Seeding

`DataSeeder.run_data_seed()` is called during the FastAPI lifespan startup event (`db/seeder.py`).

---

## Integrations

| Purpose | Provider(s) |
|---|---|
| File storage | AWS S3 (`veriprops-documents` bucket) |
| Document signing | Zoho DocSign (webhook callbacks stored in `domain/webhook/`) |
| File collaboration | Google Drive (service account auth) |
| Payments | Flutterwave, Paystack (toggle via `ACTIVE_PAYMENT_METHOD`) |
| Email | SendGrid, Mailjet |
| SMS | Twilio, Termii |
| Push notifications | Firebase, Web Push |

Email templates use Jinja2 and live in `resources/templates/`.

---

## Key Settings

Loaded from `.env.{appodus_active_env}`. Notable variables:

- `ACTIVE_DB` — `MYSQL` or `POSTGRES`
- `AUTHJWT_SECRET_KEY` — JWT signing secret
- `ACTIVE_PAYMENT_METHOD` — `FLUTTERWAVE` or `PAYSTACK`
- `ALLOWED_ORIGINS` — comma-separated CORS origins
- `AWS_S3_PRESIGNED_URL_EXPIRES` — default 900s (15 min)

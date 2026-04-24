# Bank Reconciliation SaaS — Product Requirements Document

**Client:** YCT Microfinance Bank Limited (YCTMFB) and future multi-tenant subscribers
**Document version:** 1.0
**Status:** Approved for implementation
**Last updated:** 2026-04-24
**Primary audience:** Implementing engineer(s), including AI-assisted implementation via Claude Code

---

## Document conventions

This PRD is intentionally precise. It is the source of truth for implementation. Ambiguities will produce bugs; when something is deliberately unspecified, the document says so explicitly.

- **MUST / SHALL** — a non-negotiable requirement. Failing it is a defect.
- **SHOULD** — a strong recommendation; deviations require justification in a code comment.
- **MAY** — an option left to the implementer's judgment.
- **OUT OF SCOPE** — deliberately excluded from v1. Do not implement.
- **DEFERRED** — will be added in a later version; schema should accommodate it but no functionality is required in v1.

Monetary amounts are Nigerian naira (₦) unless stated otherwise. All amounts are handled as `Decimal` with 2 decimal places of precision. Floats are forbidden for money.

Dates and times use ISO 8601. All timestamps are stored in UTC; display conversion happens at the presentation layer.

---

## Table of contents

1. Product overview
2. Glossary
3. Tenancy architecture
4. Platform-database domain model
5. Tenant-database domain model
6. State machines
7. Core algorithms
8. Rule builder DSL
9. Ingestion pipeline
10. Starting ledger wizard
11. Run workflow
12. Outputs
13. Authentication and tenancy flow
14. API surface
15. Frontend architecture
16. Testing expectations
17. Build order
18. Out of scope for v1
19. Open questions and assumptions
20. Appendix — reference data from the supplied template

---

## 1. Product overview

### 1.1 What this application is

A multi-tenant SaaS web application that automates bank reconciliation for microfinance banks. Users upload their general ledger export (the "cash book") and a corresponding bank statement; the system classifies each transaction against configurable rules, matches entries across the two sources using a scored probabilistic algorithm, surfaces unmatched and ambiguous items for human review, produces an auditor-ready Bank Reconciliation Statement (BRS), produces the supporting Notes to the BRS, and captures a preparer → reviewer → approver workflow with signatures and an immutable audit trail.

The reference client is YCTMFB, a Nigerian microfinance bank with multiple external bank relationships (WEMA, Zenith, and others). The application is designed from day one to be multi-tenant: the same codebase serves other microfinance banks as additional tenants, each with their own isolated data.

### 1.2 Who uses it

**Platform administrators** — staff of the SaaS operator. Manage tenant lifecycle (provisioning, suspension, deletion) and platform-wide configuration. Not exposed to end users.

**Tenant administrators** — staff of a subscribing microfinance bank with authority over their tenant's configuration. Invite users, assign workflow roles, configure MFA policy, manage reconciliation profiles, edit rule-sets at period boundaries.

**Preparers** — accountants who initiate reconciliation runs, upload statements, review auto-classifications, resolve match-review queues, and submit completed runs for review.

**Reviewers** — senior accountants who validate a preparer's work, accept or reject match decisions, and forward runs to approvers.

**Approvers** — heads of finance or similar, who give final sign-off on a reconciliation. Their approval freezes the run and generates the signed BRS.

A single user may hold different workflow roles on different profiles within the same tenant (e.g., preparer on WEMA, reviewer on Zenith), but not multiple workflow roles on the same run — segregation of duties is enforced at the run level.

### 1.3 Primary workflow

1. Tenant admin creates a profile for an external bank account, configures column mappings, sets opening balance, runs the starting ledger wizard.
2. Preparer uploads statements (GL export and bank statement) any time during the period. Uploads accumulate into the transaction ledger, with cross-upload deduplication by content hash.
3. At period end, the preparer initiates a reconciliation run for the period. The system pulls all un-reconciled transactions in scope, applies the frozen rule-set for that period, runs the matching engine, and produces four buckets: confident matches, variance matches (same transaction but amounts differ), review-needed, and unmatched.
4. Preparer resolves the review queue and variance matches, then submits the run for review.
5. Reviewer validates and either forwards to approver or returns to preparer.
6. Approver signs off. The run becomes immutable; transactions are flagged as reconciled. The BRS, Notes, and signed PDF are available on demand.
7. Next period: the process repeats. Reconciled transactions are excluded from future runs.

### 1.4 Product principles

Every number on the output is traceable to source transactions by drill-down. Every state change is audit-logged with actor, timestamp, and diff. Rule-sets are versioned and frozen per period so any historical BRS is perfectly reproducible. Approval produces immutable artefacts; corrections require a new run version, not a mutation of the old. Financial arithmetic uses `Decimal`, never float. Tenant isolation is enforced at the database boundary.

---

## 2. Glossary

- **Tenant** — a subscribing organization (e.g., YCTMFB). Each tenant has its own MySQL database.
- **Profile** — a (tenant internal account × external bank account) pair. Each profile has its own column mappings, rule-set, matching configuration, and BRS output template.
- **BS (Bank Statement)** — the transaction export received from the external bank for a profile. From the bank's perspective: a credit to the customer is money in; a debit is money out.
- **CB / GL (Cash Book / General Ledger)** — the tenant's internal ledger for the external bank account. From the tenant's perspective (the external bank account is an asset): a debit is money in; a credit is money out.
- **Period** — a calendar month, or a user-defined range. Reconciliations are performed per period.
- **Run** — an instance of a reconciliation performed for a profile and period. Has a lifecycle state and a full audit history.
- **Rule-set** — the collection of classification rules applicable to a profile. Versioned.
- **Rule-set version** — a frozen snapshot of a rule-set at a point in time. Each run references exactly one rule-set version.
- **Match record** — a link between a BS transaction and a CB transaction, with a score and state.
- **Variance match** — a match where TxnID correlation is strong but amounts differ beyond tolerance; requires reviewer disposition.
- **Opening balance** — the starting balance of the GL (and/or BS) at the beginning of a period, carried from the previous period or set by the starting ledger wizard.
- **Floating item** — a transaction imported via the starting ledger wizard that was already outstanding at cutover and is expected to match an entry in a future period.
- **Cutover date** — the immutable date at which a profile was initialized. No transactions dated before this date are ingested via normal upload.
- **Dedup hash** — a SHA-256 hash over canonical transaction fields used to detect duplicate rows across overlapping uploads.
- **Handoff token** — a short-lived single-use token used to establish a session on a tenant subdomain after authentication on the tenant-neutral login domain.

---

## 3. Tenancy architecture

### 3.1 Isolation model

**Database-per-tenant.** Each tenant has a dedicated MySQL database. A query executed in the context of Tenant A physically cannot see Tenant B's data, because they are on separate connection strings to separate databases. Tenant isolation is not a `WHERE` clause or an application-layer filter; it is a database boundary.

There are two distinct schemas in the system:

- **Platform database** — single, shared. Holds the tenant registry, the global user directory, platform administrators, tenant-to-database mapping, and nothing tenant-specific.
- **Tenant database template** — replicated N times, one per tenant. Holds all tenant-specific data: users, roles, profiles, transactions, runs, rule-sets, audit logs. No `tenant_id` column appears on any table in a tenant database.

### 3.2 Tenant provisioning lifecycle

Creating a tenant is a multi-step transactional operation orchestrated by a `TenantProvisioner` service:

1. Validate inputs (tenant slug uniqueness, admin email not already in `user_directory`, plan exists).
2. Insert a row into `tenants` table in the platform DB with status `PROVISIONING`.
3. Connect to MySQL as an administrative user.
4. Execute `CREATE DATABASE tenant_{slug}` with appropriate character set (`utf8mb4`) and collation (`utf8mb4_unicode_ci`).
5. Execute `CREATE USER` for the tenant's dedicated MySQL user; `GRANT ALL PRIVILEGES ON tenant_{slug}.*` to that user.
6. Store the tenant's database URL (with credentials) in the platform DB, encrypted at rest. The encryption key is held by the application (env var or secret manager reference), not in the database.
7. Run `alembic upgrade head` against the new database using the tenant migration chain.
8. Seed default rows: tenant admin user (from invite), default MFA policy (`required_for_admins`), role definitions, empty audit log entry marking provisioning complete.
9. Update tenant row status to `ACTIVE`.
10. Send invitation email to the tenant admin via SES.

If any step fails, the provisioner MUST roll back in reverse order: drop the database, drop the user, remove the platform DB row. Partial state is unacceptable. Failures are logged with enough detail to diagnose manually.

### 3.3 Connection routing

At request time, FastAPI middleware extracts the tenant context and binds a database session to that tenant's database for the lifetime of the request:

1. For requests to tenant subdomains (`yctmfb.app.com`), the tenant slug comes from the `Host` header.
2. For requests to the auth domain (`app.com` or `auth.app.com`), there is no tenant context; only platform DB operations are permitted.
3. For API requests to tenant subdomains, the JWT claims MUST include the tenant identifier; middleware verifies the JWT's tenant claim matches the subdomain.
4. Middleware queries the platform DB to resolve the tenant's database URL (cached in-process with a TTL).
5. Middleware obtains a SQLAlchemy engine for that database URL (cached per tenant, one engine per tenant) and binds a `Session` to the request context.
6. Handlers depend on `get_tenant_session` via FastAPI's dependency injection; the session is automatically the correct tenant's.

Engine caching is in-process: `Dict[tenant_slug, Engine]` with an optional max size and LRU eviction. On eviction, `engine.dispose()` is called to release pooled connections cleanly.

### 3.4 Migration strategy

Two Alembic migration chains exist:

- `migrations/platform/` — versions the platform DB schema. Applied once per deployment.
- `migrations/tenant/` — versions the tenant template schema. Applied to each tenant DB on deployment.

A deployment process MUST:

1. Apply platform migrations.
2. Enumerate all active tenants from the platform DB.
3. For each tenant, apply tenant migrations. Failure on any one tenant halts the deployment and requires manual intervention.
4. Record the migration version per tenant in the `tenants` table for operational visibility.

The `TenantProvisioner` uses the same tenant migration chain when provisioning a new tenant. The head revision of the tenant chain is always whatever the current deployment expects.

### 3.5 Background jobs and tenant context

Background workers (Dramatiq + Redis) receive job payloads that MUST include a `tenant_slug` field. Before executing job logic, the worker resolves the tenant, obtains the engine, and binds a session — the same pattern as the request middleware. A base class `TenantAwareActor` SHOULD wrap this so job implementations receive a bound session as an argument.

### 3.6 Tenant deletion and data export

**Export:** a platform admin endpoint triggers a `mysqldump` of the tenant's database, writes it to R2 under `{tenant_slug}/exports/{timestamp}.sql.gz`, encrypts at rest, and returns a presigned URL with a 24-hour expiry. DEFERRED but schema SHOULD accommodate it (a `tenant_exports` table).

**Deletion:** a platform admin endpoint marks the tenant `SCHEDULED_FOR_DELETION` with a 30-day grace period. After grace period, a scheduled job performs: final export to cold storage (if configured), `DROP DATABASE`, drop MySQL user, retain the platform `tenants` row in status `DELETED` for audit purposes (no PII remains in the platform row; only slug, dates, and the reason for deletion).

### 3.7 What crosses the boundary

Only authentication data and routing data cross the tenant boundary:

- **UserDirectory** (platform DB) contains global email → tenant mapping, password hash, MFA secret, and a pointer to the tenant user record. This is the ONLY place a cross-tenant lookup happens.
- **Tenant routing metadata** (slug, DB URL, status, plan) lives in the platform DB.
- **Platform admin accounts** live in the platform DB and never correspond to any tenant record.

Everything else — user profiles, roles, reconciliation data — lives exclusively in the tenant DB.

---

## 4. Platform-database domain model

All tables in this section live in the shared platform database.

### 4.1 `tenants`

Columns:

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `BIGINT UNSIGNED` | PK, auto-increment | |
| `slug` | `VARCHAR(63)` | UNIQUE, NOT NULL | Subdomain-safe. `[a-z0-9-]+`, 3-63 chars. |
| `display_name` | `VARCHAR(255)` | NOT NULL | Human-readable name. |
| `database_url_encrypted` | `TEXT` | NOT NULL | AES-256 encrypted connection string. |
| `status` | `ENUM('PROVISIONING', 'ACTIVE', 'SUSPENDED', 'SCHEDULED_FOR_DELETION', 'DELETED')` | NOT NULL | |
| `plan` | `ENUM('FREE', 'STARTER', 'PROFESSIONAL', 'ENTERPRISE')` | NOT NULL, default `FREE` | v1: only FREE used. Billing DEFERRED. |
| `limits_json` | `JSON` | NOT NULL, default `{}` | Per-tenant quotas. v1: unused, empty. |
| `migration_version` | `VARCHAR(32)` | NULL | Current Alembic head on the tenant DB. |
| `created_at` | `DATETIME(6)` | NOT NULL | UTC. |
| `activated_at` | `DATETIME(6)` | NULL | |
| `suspended_at` | `DATETIME(6)` | NULL | |
| `deletion_scheduled_at` | `DATETIME(6)` | NULL | |
| `deleted_at` | `DATETIME(6)` | NULL | |
| `deletion_reason` | `VARCHAR(255)` | NULL | |

Indexes: unique on `slug`; index on `status`; index on `deletion_scheduled_at` (for the scheduled-deletion sweep job).

Invariants: `slug` is immutable after row creation. `database_url_encrypted` is immutable after ACTIVE. Once status is DELETED, the row is retained forever as an audit record but holds no PII.

### 4.2 `user_directory`

The global authentication lookup table. Every user across all tenants has exactly one row here.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `BIGINT UNSIGNED` | PK, auto-increment | |
| `email` | `VARCHAR(255)` | UNIQUE, NOT NULL | Lowercased, trimmed. |
| `password_hash` | `VARCHAR(255)` | NOT NULL | argon2id format. |
| `tenant_id` | `BIGINT UNSIGNED` | NOT NULL, FK → `tenants.id` | |
| `tenant_user_id` | `BIGINT UNSIGNED` | NOT NULL | FK *into* tenant DB `users.id` — not enforced by MySQL (cross-DB). |
| `mfa_enabled` | `BOOLEAN` | NOT NULL, default FALSE | |
| `mfa_secret_encrypted` | `VARBINARY(255)` | NULL | AES-256 encrypted TOTP secret. |
| `mfa_enrolled_at` | `DATETIME(6)` | NULL | |
| `status` | `ENUM('PENDING', 'ACTIVE', 'LOCKED', 'DISABLED')` | NOT NULL, default `PENDING` | |
| `failed_login_count` | `INT UNSIGNED` | NOT NULL, default 0 | Reset on successful login. |
| `locked_until` | `DATETIME(6)` | NULL | Account lockout after N failures. |
| `last_login_at` | `DATETIME(6)` | NULL | |
| `password_changed_at` | `DATETIME(6)` | NOT NULL | |
| `created_at` | `DATETIME(6)` | NOT NULL | |
| `updated_at` | `DATETIME(6)` | NOT NULL | |

Indexes: unique on `email`; composite index on `(tenant_id, tenant_user_id)`; index on `status`.

Invariants: `email` is immutable after creation (in v1). `tenant_id` is immutable — a user cannot be moved between tenants; instead, a new account is created in the new tenant. Password hashes MUST use argon2id with parameters: time_cost=3, memory_cost=65536, parallelism=4.

### 4.3 `mfa_backup_codes`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `BIGINT UNSIGNED` | PK, auto-increment | |
| `user_directory_id` | `BIGINT UNSIGNED` | NOT NULL, FK → `user_directory.id` | |
| `code_hash` | `VARCHAR(255)` | NOT NULL | argon2id of the backup code. |
| `used_at` | `DATETIME(6)` | NULL | NULL = unused. |
| `created_at` | `DATETIME(6)` | NOT NULL | |

Indexes: index on `user_directory_id`.

Invariants: 10 codes generated at MFA enrollment. Each is single-use; `used_at` is set atomically with the login that consumes it.

### 4.4 `platform_admins`

| Column | Type | Constraints |
|---|---|---|
| `id` | `BIGINT UNSIGNED` | PK |
| `email` | `VARCHAR(255)` | UNIQUE, NOT NULL |
| `password_hash` | `VARCHAR(255)` | NOT NULL |
| `full_name` | `VARCHAR(255)` | NOT NULL |
| `mfa_enabled` | `BOOLEAN` | NOT NULL, default TRUE |
| `mfa_secret_encrypted` | `VARBINARY(255)` | NULL |
| `status` | `ENUM('ACTIVE', 'DISABLED')` | NOT NULL |
| `created_at` | `DATETIME(6)` | NOT NULL |
| `last_login_at` | `DATETIME(6)` | NULL |

Platform admins MUST enable MFA. The `mfa_enabled` default is TRUE but effective access requires `mfa_secret_encrypted IS NOT NULL`. Login flow rejects platform admins who haven't completed MFA enrollment.

### 4.5 `platform_audit_log`

Immutable record of platform-level events: tenant provisioning, tenant suspension, tenant deletion, platform admin login, platform admin actions.

| Column | Type | Constraints |
|---|---|---|
| `id` | `BIGINT UNSIGNED` | PK |
| `event_type` | `VARCHAR(64)` | NOT NULL |
| `actor_type` | `ENUM('PLATFORM_ADMIN', 'SYSTEM')` | NOT NULL |
| `actor_id` | `BIGINT UNSIGNED` | NULL |
| `tenant_id` | `BIGINT UNSIGNED` | NULL |
| `target_type` | `VARCHAR(64)` | NULL |
| `target_id` | `VARCHAR(64)` | NULL |
| `payload_json` | `JSON` | NULL |
| `ip_address` | `VARCHAR(45)` | NULL |
| `user_agent` | `VARCHAR(512)` | NULL |
| `created_at` | `DATETIME(6)` | NOT NULL |

Indexes: index on `created_at`; composite index on `(tenant_id, created_at)`; index on `event_type`.

### 4.6 `auth_sessions`

Refresh-token store. Access tokens are JWTs with short TTL; refresh tokens are opaque and stored here, revocable.

| Column | Type | Constraints |
|---|---|---|
| `id` | `CHAR(36)` | PK — UUID |
| `user_directory_id` | `BIGINT UNSIGNED` | NOT NULL, FK |
| `refresh_token_hash` | `VARCHAR(255)` | NOT NULL |
| `tenant_id` | `BIGINT UNSIGNED` | NOT NULL |
| `issued_at` | `DATETIME(6)` | NOT NULL |
| `expires_at` | `DATETIME(6)` | NOT NULL |
| `revoked_at` | `DATETIME(6)` | NULL |
| `rotated_from_id` | `CHAR(36)` | NULL, self-FK |
| `user_agent` | `VARCHAR(512)` | NULL |
| `ip_address` | `VARCHAR(45)` | NULL |

Indexes: index on `user_directory_id`; index on `expires_at`; index on `refresh_token_hash`.

Refresh tokens rotate on use: the client presents the current refresh token, the server issues a new one, and the old is marked `revoked_at`. Presenting a revoked refresh token triggers session invalidation for that user (all sessions), on the theory that a revoked token in use implies compromise.

### 4.7 `pre_auth_tokens` (Redis, not MySQL)

Short-lived tokens used between password validation and MFA completion. Stored in Redis with 5-minute TTL. Key format: `preauth:{uuid}`. Value: JSON `{user_directory_id, issued_at}`. Deleted atomically on consumption.

### 4.8 `handoff_tokens` (Redis)

Short-lived single-use tokens for the cross-subdomain handoff. 30-second TTL. Key format: `handoff:{uuid}`. Value: JSON `{user_directory_id, tenant_id, mfa_verified_at}`. Deleted atomically on consumption.

---

## 5. Tenant-database domain model

All tables in this section live in a tenant's dedicated database. No `tenant_id` column exists in any of these tables — the database itself is the tenant boundary.

### 5.1 `users`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `BIGINT UNSIGNED` | PK | Corresponds to `user_directory.tenant_user_id`. |
| `email` | `VARCHAR(255)` | UNIQUE, NOT NULL | Denormalized from user_directory for join-free display. |
| `full_name` | `VARCHAR(255)` | NOT NULL | |
| `title` | `VARCHAR(128)` | NULL | e.g. "Head of Finance". Shown in BRS signature block. |
| `is_tenant_admin` | `BOOLEAN` | NOT NULL, default FALSE | |
| `status` | `ENUM('INVITED', 'ACTIVE', 'SUSPENDED')` | NOT NULL | |
| `created_at` | `DATETIME(6)` | NOT NULL | |
| `updated_at` | `DATETIME(6)` | NOT NULL | |
| `invited_by_user_id` | `BIGINT UNSIGNED` | NULL, self-FK | |

Indexes: unique on `email`; index on `status`.

Invariants: `users.id` MUST equal `user_directory.tenant_user_id` for the corresponding `user_directory` row. `users.email` MUST equal `user_directory.email` (kept in sync on update via application logic).

### 5.2 `profiles`

A profile is a (tenant internal account × external bank account) pair.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `BIGINT UNSIGNED` | PK | |
| `code` | `VARCHAR(32)` | UNIQUE, NOT NULL | e.g. "WEMA-MAIN". User-chosen. |
| `display_name` | `VARCHAR(255)` | NOT NULL | |
| `external_bank_name` | `VARCHAR(128)` | NOT NULL | e.g. "WEMA Bank". |
| `external_account_number` | `VARCHAR(32)` | NOT NULL | |
| `internal_gl_account_code` | `VARCHAR(64)` | NULL | Tenant's internal ledger code for this account. |
| `currency` | `CHAR(3)` | NOT NULL, default 'NGN' | ISO 4217. |
| `cutover_date` | `DATE` | NULL | Set by starting ledger wizard. Immutable after set. |
| `opening_balance` | `DECIMAL(20, 2)` | NULL | Initial balance at cutover. |
| `active_ruleset_version_id` | `BIGINT UNSIGNED` | NULL, FK → `ruleset_versions.id` | |
| `matching_config_json` | `JSON` | NOT NULL | Thresholds, weights, clearing window. |
| `brs_template_json` | `JSON` | NOT NULL | BRS line mapping and layout. |
| `status` | `ENUM('DRAFT', 'INITIALIZED', 'ACTIVE', 'ARCHIVED')` | NOT NULL | |
| `created_at` | `DATETIME(6)` | NOT NULL | |
| `created_by_user_id` | `BIGINT UNSIGNED` | NOT NULL, FK → `users.id` | |
| `updated_at` | `DATETIME(6)` | NOT NULL | |

Indexes: unique on `code`; index on `status`.

Invariants: `cutover_date` is immutable once set. Status transitions: DRAFT → INITIALIZED (after starting ledger wizard completes) → ACTIVE (after first run). ARCHIVED is terminal; no new runs permitted.

Default `matching_config_json`:

```json
{
  "weights": {
    "txnid": 0.4,
    "amount": 0.3,
    "date": 0.2,
    "narration": 0.1
  },
  "thresholds": {
    "confident": 0.85,
    "variance_min": 0.70,
    "review_min": 0.50
  },
  "amount_tolerance": {
    "absolute_ngn": 1000,
    "relative_pct": 0.1
  },
  "clearing_window_days": 15,
  "narration_fuzzy_min": 0.70
}
```

### 5.3 `column_mappings`

Versioned column mapping for a profile's uploaded files. One mapping per (profile, side) per version. A new version is created whenever the upload format changes.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `BIGINT UNSIGNED` | PK | |
| `profile_id` | `BIGINT UNSIGNED` | NOT NULL, FK | |
| `side` | `ENUM('BS', 'CB')` | NOT NULL | |
| `version` | `INT UNSIGNED` | NOT NULL | Per (profile, side). Monotonic. |
| `header_signature` | `VARCHAR(64)` | NOT NULL | SHA-256 of normalized header row. |
| `mapping_json` | `JSON` | NOT NULL | See below. |
| `opening_balance_cell` | `VARCHAR(32)` | NULL | e.g. "C7" — where to read opening balance from this format. |
| `is_active` | `BOOLEAN` | NOT NULL | |
| `created_at` | `DATETIME(6)` | NOT NULL | |
| `created_by_user_id` | `BIGINT UNSIGNED` | NOT NULL, FK | |

Indexes: unique on `(profile_id, side, version)`; index on `(profile_id, side, header_signature)`.

`mapping_json` structure:

```json
{
  "header_row": 4,
  "data_start_row": 5,
  "columns": {
    "date": {"source_column": "A", "format": "MM/DD/YYYY"},
    "txnid": {"source_column": "B"},
    "narration": {"source_column": "C"},
    "debit": {"source_column": "D", "parser": "ngn_text"},
    "credit": {"source_column": "E", "parser": "ngn_text"},
    "balance": {"source_column": "F", "parser": "ngn_text", "optional": true}
  },
  "skip_if_row_matches": [
    {"column": "A", "equals": "TOTAL"},
    {"column": "A", "starts_with": "Summary"}
  ]
}
```

Parsers: `ngn_text` (strips commas, handles decimals), `numeric` (already numeric), `date_iso`, `date_us` (MM/DD/YYYY), `date_european` (DD/MM/YYYY).

### 5.4 `ruleset_versions`

| Column | Type | Constraints |
|---|---|---|
| `id` | `BIGINT UNSIGNED` | PK |
| `profile_id` | `BIGINT UNSIGNED` | NOT NULL, FK |
| `version_number` | `INT UNSIGNED` | NOT NULL |
| `status` | `ENUM('DRAFT', 'ACTIVE', 'FROZEN', 'ARCHIVED')` | NOT NULL |
| `effective_from_period_start` | `DATE` | NULL |
| `created_at` | `DATETIME(6)` | NOT NULL |
| `created_by_user_id` | `BIGINT UNSIGNED` | NOT NULL, FK |
| `activated_at` | `DATETIME(6)` | NULL |
| `frozen_at` | `DATETIME(6)` | NULL |
| `notes` | `TEXT` | NULL |

Indexes: unique on `(profile_id, version_number)`; index on `(profile_id, status)`.

Status transitions:
- DRAFT: editable, not in use.
- ACTIVE: current version applied to new runs.
- FROZEN: attached to one or more completed runs; immutable.
- ARCHIVED: superseded, retained for audit only.

At most one version per profile is ACTIVE at a time. Activating a new version transitions the previous ACTIVE to FROZEN or ARCHIVED depending on whether runs reference it.

### 5.5 `rules`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `BIGINT UNSIGNED` | PK | |
| `ruleset_version_id` | `BIGINT UNSIGNED` | NOT NULL, FK | |
| `priority` | `INT UNSIGNED` | NOT NULL | Lower priority evaluated first. |
| `name` | `VARCHAR(255)` | NOT NULL | Human-readable. |
| `side` | `ENUM('BS', 'CB', 'BOTH')` | NOT NULL | Which side this rule applies to. |
| `dr_cr` | `ENUM('DEBIT', 'CREDIT', 'ANY')` | NOT NULL | Restrict by transaction direction. |
| `condition_json` | `JSON` | NOT NULL | Condition tree; see Section 8. |
| `target_category` | `VARCHAR(64)` | NOT NULL | One of the BRS category codes. |
| `is_enabled` | `BOOLEAN` | NOT NULL, default TRUE | |
| `created_at` | `DATETIME(6)` | NOT NULL | |

Indexes: composite index on `(ruleset_version_id, priority)`; FK indexes.

### 5.6 `uploads`

| Column | Type | Constraints |
|---|---|---|
| `id` | `CHAR(36)` | PK — UUID |
| `profile_id` | `BIGINT UNSIGNED` | NOT NULL, FK |
| `side` | `ENUM('BS', 'CB')` | NOT NULL |
| `uploaded_by_user_id` | `BIGINT UNSIGNED` | NOT NULL, FK |
| `original_filename` | `VARCHAR(512)` | NOT NULL |
| `file_size_bytes` | `BIGINT UNSIGNED` | NOT NULL |
| `content_type` | `VARCHAR(128)` | NOT NULL |
| `r2_key` | `VARCHAR(512)` | NOT NULL |
| `r2_etag` | `VARCHAR(128)` | NULL |
| `status` | `ENUM('RECEIVED', 'PARSING', 'PARSED', 'INGESTING', 'INGESTED', 'FAILED')` | NOT NULL |
| `rows_parsed` | `INT UNSIGNED` | NULL |
| `rows_new` | `INT UNSIGNED` | NULL |
| `rows_duplicate` | `INT UNSIGNED` | NULL |
| `rows_rejected` | `INT UNSIGNED` | NULL |
| `error_json` | `JSON` | NULL |
| `column_mapping_id` | `BIGINT UNSIGNED` | NULL, FK |
| `period_covered_start` | `DATE` | NULL |
| `period_covered_end` | `DATE` | NULL |
| `created_at` | `DATETIME(6)` | NOT NULL |
| `completed_at` | `DATETIME(6)` | NULL |

Indexes: index on `profile_id`; index on `status`; index on `created_at`.

R2 key format: `{tenant_slug}/{profile_id}/uploads/{YYYY}/{MM}/{upload_uuid}.{ext}`.

### 5.7 `transactions`

This is the central ledger. Every row ever ingested from any upload becomes a row here. Deduplication is by `dedup_hash`.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `BIGINT UNSIGNED` | PK, auto-increment | |
| `profile_id` | `BIGINT UNSIGNED` | NOT NULL, FK | |
| `side` | `ENUM('BS', 'CB')` | NOT NULL | |
| `upload_id` | `CHAR(36)` | NOT NULL, FK | The upload that introduced this row. |
| `transaction_date` | `DATE` | NOT NULL | |
| `posting_date` | `DATE` | NULL | If the source provides separate transaction vs posting dates. |
| `txn_id_raw` | `VARCHAR(64)` | NOT NULL | As parsed from source. |
| `txn_id_normalized` | `VARCHAR(64)` | NOT NULL | Trimmed, uppercased. Used for matching. |
| `narration` | `TEXT` | NOT NULL | Preserved original. |
| `narration_normalized` | `TEXT` | NOT NULL | Uppercased, whitespace normalized. |
| `debit_amount` | `DECIMAL(20, 2)` | NOT NULL, default 0 | |
| `credit_amount` | `DECIMAL(20, 2)` | NOT NULL, default 0 | |
| `running_balance` | `DECIMAL(20, 2)` | NULL | Source-provided balance if available. |
| `dedup_hash` | `CHAR(64)` | NOT NULL | SHA-256 hex. See Section 7.4. |
| `source_category` | `VARCHAR(64)` | NULL | "previous_month" or NULL; see Section 7.6. |
| `category` | `VARCHAR(64)` | NULL | Populated by classification engine. |
| `category_rule_id` | `BIGINT UNSIGNED` | NULL, FK → `rules.id` | Rule that classified it. |
| `status` | `ENUM('PENDING', 'CLASSIFIED', 'MATCHED', 'VARIANCE_MATCHED', 'UNMATCHED', 'RECONCILED', 'EXCLUDED')` | NOT NULL | |
| `run_id` | `BIGINT UNSIGNED` | NULL, FK → `runs.id` | Set when included in a run. |
| `is_floating_seed` | `BOOLEAN` | NOT NULL, default FALSE | TRUE for rows imported via starting ledger wizard. |
| `created_at` | `DATETIME(6)` | NOT NULL | |
| `updated_at` | `DATETIME(6)` | NOT NULL | |

Indexes:
- unique on `dedup_hash`
- composite on `(profile_id, side, transaction_date)` — primary query path
- composite on `(profile_id, side, status)`
- composite on `(profile_id, side, txn_id_normalized)` — for matching pre-filter
- FULLTEXT on `narration_normalized` — for matching fuzzy pre-filter
- index on `run_id`

Constraint: exactly one of `debit_amount`, `credit_amount` is > 0 in normal cases; both being zero is permitted only for zero-value informational entries (rare; flag as warning).

Status transitions are defined in Section 6.2.

### 5.8 `runs`

| Column | Type | Constraints |
|---|---|---|
| `id` | `BIGINT UNSIGNED` | PK |
| `profile_id` | `BIGINT UNSIGNED` | NOT NULL, FK |
| `period_start` | `DATE` | NOT NULL |
| `period_end` | `DATE` | NOT NULL |
| `ruleset_version_id` | `BIGINT UNSIGNED` | NOT NULL, FK |
| `opening_balance_gl` | `DECIMAL(20, 2)` | NOT NULL |
| `opening_balance_bs` | `DECIMAL(20, 2)` | NOT NULL |
| `closing_balance_gl` | `DECIMAL(20, 2)` | NULL |
| `closing_balance_bs` | `DECIMAL(20, 2)` | NULL |
| `state` | `ENUM('DRAFT', 'CLASSIFYING', 'MATCHING', 'REVIEW_READY', 'UNDER_REVIEW', 'APPROVAL_READY', 'APPROVED', 'PUBLISHED', 'RETURNED_TO_PREPARER', 'SUPERSEDED')` | NOT NULL |
| `preparer_user_id` | `BIGINT UNSIGNED` | NOT NULL, FK → `users.id` |
| `reviewer_user_id` | `BIGINT UNSIGNED` | NULL, FK → `users.id` |
| `approver_user_id` | `BIGINT UNSIGNED` | NULL, FK → `users.id` |
| `preparer_signed_at` | `DATETIME(6)` | NULL |
| `reviewer_signed_at` | `DATETIME(6)` | NULL |
| `approver_signed_at` | `DATETIME(6)` | NULL |
| `superseded_by_run_id` | `BIGINT UNSIGNED` | NULL, self-FK |
| `computed_totals_json` | `JSON` | NULL | Cached BRS line totals post-match. |
| `notes` | `TEXT` | NULL | Free-text notes from preparer. |
| `created_at` | `DATETIME(6)` | NOT NULL |
| `updated_at` | `DATETIME(6)` | NOT NULL |
| `submitted_to_review_at` | `DATETIME(6)` | NULL |
| `submitted_to_approval_at` | `DATETIME(6)` | NULL |
| `published_at` | `DATETIME(6)` | NULL |

Indexes: composite on `(profile_id, period_start, period_end)`; index on `state`; index on `superseded_by_run_id`.

Segregation-of-duties constraint (application-enforced, with a CHECK if supported):
- `preparer_user_id` != `reviewer_user_id`
- `preparer_user_id` != `approver_user_id`
- `reviewer_user_id` != `approver_user_id` (when both set)

State machine defined in Section 6.1.

### 5.9 `match_records`

A match record represents a proposed or confirmed pairing between a BS transaction and a CB transaction.

| Column | Type | Constraints |
|---|---|---|
| `id` | `BIGINT UNSIGNED` | PK |
| `run_id` | `BIGINT UNSIGNED` | NOT NULL, FK |
| `bs_transaction_id` | `BIGINT UNSIGNED` | NOT NULL, FK → `transactions.id` |
| `cb_transaction_id` | `BIGINT UNSIGNED` | NOT NULL, FK → `transactions.id` |
| `score` | `DECIMAL(6, 4)` | NOT NULL | In [0, 1]. |
| `txnid_subscore` | `DECIMAL(6, 4)` | NOT NULL |
| `amount_subscore` | `DECIMAL(6, 4)` | NOT NULL |
| `date_subscore` | `DECIMAL(6, 4)` | NOT NULL |
| `narration_subscore` | `DECIMAL(6, 4)` | NOT NULL |
| `amount_delta` | `DECIMAL(20, 2)` | NOT NULL | bs.amount − cb.amount. |
| `date_delta_days` | `INT` | NOT NULL | cb.date − bs.date in days. |
| `bucket` | `ENUM('CONFIDENT', 'VARIANCE', 'REVIEW', 'REJECTED', 'ACCEPTED')` | NOT NULL |
| `reviewer_disposition` | `ENUM('ACCEPTED', 'REJECTED', 'DEFERRED', null)` | NULL |
| `reviewer_user_id` | `BIGINT UNSIGNED` | NULL, FK |
| `reviewer_note` | `VARCHAR(1024)` | NULL |
| `reviewed_at` | `DATETIME(6)` | NULL |
| `created_at` | `DATETIME(6)` | NOT NULL |

Indexes: composite on `(run_id, bucket)`; index on `bs_transaction_id`; index on `cb_transaction_id`.

Invariants: unique-assignment — within a single run, a given BS transaction may appear in AT MOST ONE accepted match record, and likewise for CB. Proposed matches may be one-to-many until reviewer resolves, but the auto-matcher must also enforce this when materializing auto-accepted pairs (see Section 7.2).

### 5.10 `signing_records`

Immutable record of each state-change signature in the run lifecycle.

| Column | Type | Constraints |
|---|---|---|
| `id` | `BIGINT UNSIGNED` | PK |
| `run_id` | `BIGINT UNSIGNED` | NOT NULL, FK |
| `role` | `ENUM('PREPARER', 'REVIEWER', 'APPROVER')` | NOT NULL |
| `user_id` | `BIGINT UNSIGNED` | NOT NULL, FK |
| `user_name_snapshot` | `VARCHAR(255)` | NOT NULL |
| `user_title_snapshot` | `VARCHAR(128)` | NULL |
| `signed_at` | `DATETIME(6)` | NOT NULL |
| `ip_address` | `VARCHAR(45)` | NULL |
| `user_agent` | `VARCHAR(512)` | NULL |
| `content_hash` | `CHAR(64)` | NOT NULL | SHA-256 of the run's computed_totals_json at signing. |

Indexes: composite on `(run_id, role)`; unique on `(run_id, role)`.

Name and title are snapshotted so that changing a user's profile later doesn't alter historical signing records.

### 5.11 `audit_log`

Immutable record of every state-changing action in the tenant.

| Column | Type | Constraints |
|---|---|---|
| `id` | `BIGINT UNSIGNED` | PK |
| `event_type` | `VARCHAR(64)` | NOT NULL |
| `actor_user_id` | `BIGINT UNSIGNED` | NULL, FK |
| `target_type` | `VARCHAR(64)` | NOT NULL |
| `target_id` | `VARCHAR(64)` | NOT NULL |
| `diff_json` | `JSON` | NULL |
| `metadata_json` | `JSON` | NULL |
| `ip_address` | `VARCHAR(45)` | NULL |
| `user_agent` | `VARCHAR(512)` | NULL |
| `created_at` | `DATETIME(6)` | NOT NULL |

Indexes: index on `created_at`; composite on `(target_type, target_id, created_at)`; index on `actor_user_id`; index on `event_type`.

Event types: USER_INVITED, USER_ACTIVATED, USER_ROLE_ASSIGNED, USER_ROLE_REVOKED, PROFILE_CREATED, PROFILE_UPDATED, COLUMN_MAPPING_CREATED, RULESET_VERSION_CREATED, RULESET_VERSION_ACTIVATED, RULE_CREATED, RULE_UPDATED, RULE_DELETED, UPLOAD_STARTED, UPLOAD_COMPLETED, UPLOAD_FAILED, RUN_CREATED, RUN_STATE_CHANGED, MATCH_REVIEWED, MATCH_OVERRIDDEN, RUN_SIGNED, STARTING_LEDGER_IMPORTED, MFA_POLICY_CHANGED.

### 5.12 `role_assignments`

Per-profile workflow role assignments.

| Column | Type | Constraints |
|---|---|---|
| `id` | `BIGINT UNSIGNED` | PK |
| `user_id` | `BIGINT UNSIGNED` | NOT NULL, FK |
| `profile_id` | `BIGINT UNSIGNED` | NOT NULL, FK |
| `role` | `ENUM('PREPARER', 'REVIEWER', 'APPROVER')` | NOT NULL |
| `granted_by_user_id` | `BIGINT UNSIGNED` | NOT NULL, FK |
| `granted_at` | `DATETIME(6)` | NOT NULL |
| `revoked_at` | `DATETIME(6)` | NULL |

Indexes: unique on `(user_id, profile_id, role, revoked_at)` with NULL-treating-as-distinct emulation (MySQL allows multiple NULLs in a unique index by default; we rely on that to permit re-grant after revoke). composite on `(profile_id, role, revoked_at)`.

A user's effective roles are: set of `role` where `revoked_at IS NULL`.

### 5.13 `opening_balances`

Historical opening balances per (profile, period_start). Allows override audit.

| Column | Type | Constraints |
|---|---|---|
| `id` | `BIGINT UNSIGNED` | PK |
| `profile_id` | `BIGINT UNSIGNED` | NOT NULL, FK |
| `period_start` | `DATE` | NOT NULL |
| `side` | `ENUM('GL', 'BS')` | NOT NULL |
| `amount` | `DECIMAL(20, 2)` | NOT NULL |
| `source` | `ENUM('CARRIED_FORWARD', 'FILE', 'MANUAL', 'WIZARD')` | NOT NULL |
| `source_upload_id` | `CHAR(36)` | NULL, FK |
| `set_by_user_id` | `BIGINT UNSIGNED` | NOT NULL, FK |
| `set_at` | `DATETIME(6)` | NOT NULL |
| `superseded_at` | `DATETIME(6)` | NULL |

Indexes: composite on `(profile_id, period_start, side, superseded_at)`.

Multiple rows per (profile, period_start, side) are permitted across time; the row with `superseded_at IS NULL` is the current value. Supersession records the full history of overrides.

### 5.14 `mfa_policy`

Per-tenant MFA policy. Single-row table.

| Column | Type | Constraints |
|---|---|---|
| `id` | `TINYINT UNSIGNED` | PK — always 1 |
| `tier` | `ENUM('OPTIONAL', 'REQUIRED_FOR_ADMINS', 'REQUIRED_FOR_ALL')` | NOT NULL, default 'REQUIRED_FOR_ADMINS' |
| `updated_at` | `DATETIME(6)` | NOT NULL |
| `updated_by_user_id` | `BIGINT UNSIGNED` | NOT NULL, FK |

---


## 6. State machines

### 6.1 Run lifecycle

States: `DRAFT`, `CLASSIFYING`, `MATCHING`, `REVIEW_READY`, `UNDER_REVIEW`, `APPROVAL_READY`, `APPROVED`, `PUBLISHED`, `RETURNED_TO_PREPARER`, `SUPERSEDED`.

Transitions (`from state → event → to state`, with preconditions and side effects):

| From | Event | To | Actor | Preconditions | Side effects |
|---|---|---|---|---|---|
| — | `CREATE_RUN` | `DRAFT` | Preparer | User has PREPARER role on profile; no ACTIVE run for (profile, period) | Create Run row; assign preparer |
| `DRAFT` | `RUN_CLASSIFICATION` | `CLASSIFYING` | Preparer / System | Profile has active ruleset version | Enqueue classification job |
| `CLASSIFYING` | `CLASSIFICATION_COMPLETE` | `MATCHING` | System | All in-scope transactions have `status=CLASSIFIED` or `EXCLUDED` | Enqueue matching job |
| `CLASSIFYING` | `CLASSIFICATION_FAILED` | `DRAFT` | System | — | Record error; notify preparer |
| `MATCHING` | `MATCHING_COMPLETE` | `REVIEW_READY` | System | Matching job done | Compute totals; persist to `runs.computed_totals_json` |
| `MATCHING` | `MATCHING_FAILED` | `DRAFT` | System | — | Record error |
| `REVIEW_READY` | `SUBMIT_FOR_REVIEW` | `UNDER_REVIEW` | Preparer | Preparer has resolved all REVIEW bucket items | Write SigningRecord (PREPARER); set `preparer_signed_at` |
| `UNDER_REVIEW` | `RETURN_TO_PREPARER` | `RETURNED_TO_PREPARER` | Reviewer | Reviewer has REVIEWER role on profile; reviewer != preparer | Clear reviewer_signed_at; notify preparer |
| `UNDER_REVIEW` | `SUBMIT_FOR_APPROVAL` | `APPROVAL_READY` | Reviewer | All VARIANCE items disposed; reviewer != preparer | Write SigningRecord (REVIEWER); set `reviewer_signed_at` |
| `APPROVAL_READY` | `RETURN_TO_REVIEWER` | `UNDER_REVIEW` | Approver | Approver has APPROVER role; approver ∉ {preparer, reviewer} | Clear approver_signed_at |
| `APPROVAL_READY` | `APPROVE` | `APPROVED` | Approver | Approver has APPROVER role; approver ∉ {preparer, reviewer} | Write SigningRecord (APPROVER); set `approver_signed_at`; flip all in-run transactions to `status=RECONCILED`; freeze ruleset version |
| `APPROVED` | `PUBLISH` | `PUBLISHED` | Approver (auto) | — | Run is final; outputs renderable |
| `APPROVED`, `PUBLISHED` | `SUPERSEDE` | `SUPERSEDED` | Tenant Admin | New run created for same period | Set `superseded_by_run_id`; retain all data |
| `RETURNED_TO_PREPARER` | `RESUBMIT` | `UNDER_REVIEW` | Preparer | Preparer has addressed reviewer's concerns | Overwrite PREPARER signing record |

Back-transitions (RETURN_TO_PREPARER, RETURN_TO_REVIEWER) invalidate downstream signing records and audit-log the revocation.

Terminal states: `PUBLISHED` (normal), `SUPERSEDED` (replaced by new version). Nothing may transition out of these.

An attempt to transition from an unlisted (from, event) pair MUST raise a `IllegalStateTransition` error and be rejected at the API layer with HTTP 409 Conflict.

### 6.2 Transaction status

States: `PENDING`, `CLASSIFIED`, `MATCHED`, `VARIANCE_MATCHED`, `UNMATCHED`, `RECONCILED`, `EXCLUDED`.

| From | Event | To | Notes |
|---|---|---|---|
| — | `INGEST` | `PENDING` | On upload commit |
| `PENDING` | `CLASSIFY` | `CLASSIFIED` | During run classification phase |
| `PENDING` | `EXCLUDE` | `EXCLUDED` | Rule marks it out-of-scope (e.g. opening balance rows) |
| `CLASSIFIED` | `MATCH_CONFIDENT` | `MATCHED` | |
| `CLASSIFIED` | `MATCH_VARIANCE` | `VARIANCE_MATCHED` | |
| `CLASSIFIED` | `MATCH_FAILED` | `UNMATCHED` | No candidate scored above review threshold |
| `MATCHED`, `VARIANCE_MATCHED`, `UNMATCHED` | `RECONCILE` | `RECONCILED` | On run approval |
| `MATCHED`, `VARIANCE_MATCHED` | `REVERT` | `CLASSIFIED` | On run return to preparer |
| `RECONCILED` | — | — | Terminal |

`RECONCILED` is terminal. A transaction reconciled in one run cannot be pulled into another run.

### 6.3 Upload lifecycle

States: `RECEIVED`, `PARSING`, `PARSED`, `INGESTING`, `INGESTED`, `FAILED`.

| From | Event | To | Notes |
|---|---|---|---|
| — | `UPLOAD_STARTED` | `RECEIVED` | After successful R2 write |
| `RECEIVED` | `PARSE_STARTED` | `PARSING` | Background job picks up |
| `PARSING` | `PARSE_SUCCESS` | `PARSED` | Rows extracted to memory or staging |
| `PARSING` | `PARSE_ERROR` | `FAILED` | Record error_json |
| `PARSED` | `INGEST_STARTED` | `INGESTING` | Dedup + insert |
| `INGESTING` | `INGEST_SUCCESS` | `INGESTED` | Populate rows_new, rows_duplicate |
| `INGESTING` | `INGEST_ERROR` | `FAILED` | Record error_json |

Retry: `FAILED` uploads may be retried by the user (new upload, same file). They are not automatically retried.

### 6.4 Match record state

States: `PROPOSED`, `CONFIDENT`, `VARIANCE`, `REVIEW`, `REJECTED`, `ACCEPTED`.

The matcher initially creates records in `PROPOSED` state. The bucketing pass assigns them to `CONFIDENT`, `VARIANCE`, `REVIEW` based on score thresholds. `CONFIDENT` records are auto-accepted into `ACCEPTED` if the unique-assignment constraint permits; otherwise they drop to `REVIEW`. Reviewer disposition transitions `VARIANCE` and `REVIEW` records to `ACCEPTED` or `REJECTED`.

### 6.5 User / UserDirectory lifecycle

UserDirectory status: `PENDING` → `ACTIVE` (on first password set) → `LOCKED` (after N failures) or `DISABLED` (admin action). `LOCKED` auto-unlocks after `locked_until` passes.

Tenant `users` status: `INVITED` → `ACTIVE` (on first login) → `SUSPENDED` (admin action; users retain audit history but cannot log in).

---

## 7. Core algorithms

### 7.1 Classification engine

Classification assigns a category to each transaction based on the ruleset. Single pass, in-memory per run.

**Algorithm:**

```
function classify_transactions(run_id, transactions, ruleset_version):
  rules = load_rules(ruleset_version.id, enabled=True, order_by=priority)
  for txn in transactions:
    assigned = False
    for rule in rules:
      if rule.side != 'BOTH' and rule.side != txn.side:
        continue
      if rule.dr_cr != 'ANY':
        if rule.dr_cr == 'DEBIT' and txn.debit_amount == 0:
          continue
        if rule.dr_cr == 'CREDIT' and txn.credit_amount == 0:
          continue
      if evaluate_condition(rule.condition_json, txn):
        txn.category = rule.target_category
        txn.category_rule_id = rule.id
        txn.status = 'CLASSIFIED'
        assigned = True
        break
    if not assigned:
      # Fallback: generic BS/CB debit/credit categories
      if txn.side == 'BS':
        txn.category = 'BS_DEBIT' if txn.debit_amount > 0 else 'BS_CREDIT'
      else:
        txn.category = 'CB_DEBIT' if txn.debit_amount > 0 else 'CB_CREDIT'
      txn.status = 'CLASSIFIED'
    bulk_update(txn)
```

**Condition evaluation** (`evaluate_condition`): recursive evaluation of the condition tree defined in Section 8. Returns boolean.

**Complexity:** O(N × R) where N = transactions in scope, R = rules. At 500k transactions × 30 rules = 15M evaluations. Each evaluation is cheap (string contains, regex against narration, amount comparison). Target: under 10 seconds.

### 7.2 Matching engine

Matching is the most complex algorithm. Goal: for each unmatched BS transaction, find the best CB counterpart (or vice versa), producing scored match records.

**Phase 1 — Candidate generation (indexed pre-filter).**

For each BS transaction, generate a candidate set of CB transactions that could plausibly match. The candidate set is the UNION of:

- CB transactions where `txn_id_normalized` appears as a substring of `narration_normalized` OR `narration_normalized` contains `txn_id_normalized`.
- CB transactions where `ABS(amount - bs.amount) <= max(matching_config.amount_tolerance.absolute_ngn, amount * matching_config.amount_tolerance.relative_pct / 100)` AND `date` is within `[bs.date, bs.date + clearing_window_days]`.
- CB transactions matching a FULLTEXT search against `narration_normalized` with the BS `txn_id_normalized` as the query.

Use indexed queries only. Do not scan the full table. Deduplicate candidates.

**Phase 2 — Scoring.**

For each (BS, CB) candidate pair, compute subscores:

```
txnid_subscore:
  if bs.txn_id_normalized == cb.txn_id_normalized: 1.0
  elif bs.txn_id_normalized in cb.narration_normalized: 0.9
  elif cb.txn_id_normalized in bs.narration_normalized: 0.9
  elif fuzzy_ratio(bs.txn_id, cb.txn_id) >= 0.85: 0.6
  else: 0.0

amount_subscore:
  bs_amt = bs.debit_amount + bs.credit_amount  # one is always 0
  cb_amt = cb.debit_amount + cb.credit_amount
  delta = abs(bs_amt - cb_amt)
  tol = max(amount_tolerance.absolute_ngn, bs_amt * amount_tolerance.relative_pct / 100)
  if delta == 0: 1.0
  elif delta <= tol: 1.0 - (delta / tol) * 0.5  # within tolerance, scaled
  else: 0.0

date_subscore:
  days = abs((cb.transaction_date - bs.transaction_date).days)
  if days == 0: 1.0
  elif days <= clearing_window_days:
    # Directional preference: CB later than BS is typical clearing
    if cb.transaction_date >= bs.transaction_date:
      1.0 - (days / clearing_window_days) * 0.3  # mild penalty
    else:
      1.0 - (days / clearing_window_days) * 0.7  # stronger penalty
  else: 0.0

narration_subscore:
  fuzzy_ratio(bs.narration_normalized, cb.narration_normalized)  # rapidfuzz token_set_ratio / 100
```

**Phase 3 — Weighted combination.**

```
score = (
  weights.txnid     * txnid_subscore +
  weights.amount    * amount_subscore +
  weights.date      * date_subscore +
  weights.narration * narration_subscore
)
```

Default weights sum to 1.0; score is in [0, 1].

**Phase 4 — Sign-polarity check.**

For a valid match, the transactions must represent the same real-world event. Given the sign conventions:

- BS credit + CB debit = inflow event (valid match)
- BS debit + CB credit = outflow event (valid match)
- BS credit + CB credit OR BS debit + CB debit = REJECT regardless of score

Sign-polarity failure sets `bucket = 'REJECTED'` and `score = 0.0`.

**Phase 5 — Bucket assignment.**

```
if score >= thresholds.confident and amount_subscore >= 0.99: bucket = CONFIDENT
elif score >= thresholds.variance_min and txnid_subscore >= 0.8 and amount_subscore < 1.0: bucket = VARIANCE
elif score >= thresholds.review_min: bucket = REVIEW
else: do not create match record (BS/CB remains UNMATCHED)
```

**Phase 6 — Unique-assignment resolution.**

Multiple BS transactions may have CONFIDENT matches to the same CB transaction (or vice versa). Resolve via Hungarian-algorithm-style assignment: for each contested CB, choose the BS partner with highest score; demote losers to REVIEW.

Practical implementation: sort all CONFIDENT candidate pairs by score DESC; greedily accept pairs where neither side is already accepted; demote the rest. This is approximate but sufficient for real-world volumes.

**Phase 7 — Materialize match records.**

Insert `match_records` rows with scores, subscores, deltas, and bucket. Update transaction statuses:

- Both sides of an accepted CONFIDENT or VARIANCE match: `MATCHED` or `VARIANCE_MATCHED`.
- Sides present in any REVIEW record: remain `CLASSIFIED`.
- Sides in no surviving match records: `UNMATCHED`.

**Performance target:** for 100k BS × 500k CB (realistic monthly scale with drip-feed), candidate generation via indexes limits each BS to typically < 50 candidates, so 5M candidate pair evaluations. Target: under 60 seconds.

### 7.3 BRS composition

Given an approved run's transactions and matches, compose the BRS line totals.

**Data inputs:**
- Opening balance GL, Opening balance BS (from run)
- All transactions in run (with status, side, category, amounts)
- All match records for run
- `brs_template_json` from profile

**Outputs (computed_totals_json):**

```json
{
  "gl_closing_balance": 207078584.61,
  "credit_items": {
    "credit_bs_not_in_gl": 30022077.79,
    "remita_bulk_credit": 16000.00,
    "credit_cb_not_in_bs": 0.00,
    "total": 30038077.79
  },
  "subtotal_after_credits": 237116662.40,
  "debit_items": {
    "debit_bs_not_in_gl": 200000000.00,
    "remita_wallet_topup": 3000150.00,
    "debit_cb_not_in_bs": 3511028.71,
    "total": 206511178.71
  },
  "subtotal_after_debits": 30605483.69,
  "recurrent_charges": {
    "account_maintenance": 3225.38,
    "electronic_money_transfer": 250.00,
    "transfer_charges": 215.00,
    "total": 3690.38
  },
  "gl_adjusted_balance": 30601793.31,
  "difference": 18529758.01,
  "bs_closing_balance": 49131551.32,
  "informational": {
    "previous_month_items": 5239533.67,
    "variance_total": 0.00
  }
}
```

**Algorithm:**

```
function compose_brs(run):
  txns = load_transactions(run_id=run.id, exclude_status=['EXCLUDED'])
  matches = load_match_records(run_id=run.id, bucket_in=['CONFIDENT', 'VARIANCE', 'ACCEPTED'])

  matched_bs_ids = {m.bs_transaction_id for m in matches if m.bucket != 'REJECTED'}
  matched_cb_ids = {m.cb_transaction_id for m in matches if m.bucket != 'REJECTED'}

  buckets = {}
  for txn in txns:
    key = (txn.side, txn.category)
    is_matched = (txn.id in matched_bs_ids) if txn.side == 'BS' else (txn.id in matched_cb_ids)
    is_floating = txn.is_floating_seed
    signed_amount = txn.debit_amount - txn.credit_amount if txn.side == 'BS' else txn.credit_amount - txn.debit_amount
    # Apply BRS template mapping
    brs_line = resolve_brs_line(profile.brs_template_json, txn.side, txn.category, is_matched, is_floating)
    if brs_line is not None:
      buckets[brs_line] = buckets.get(brs_line, 0) + abs(signed_amount)

  totals = {
    "gl_closing_balance": run.opening_balance_gl + sum_of_cb_transactions(txns),
    "credit_items": extract_credit_items(buckets),
    "debit_items": extract_debit_items(buckets),
    "recurrent_charges": extract_charges(buckets)
  }
  totals.subtotal_after_credits = totals.gl_closing_balance + totals.credit_items.total
  totals.subtotal_after_debits = totals.subtotal_after_credits - totals.debit_items.total
  totals.gl_adjusted_balance = totals.subtotal_after_debits - totals.recurrent_charges.total
  totals.bs_closing_balance = run.opening_balance_bs + sum_of_bs_transactions(txns)
  totals.difference = totals.bs_closing_balance - totals.gl_adjusted_balance
  return totals
```

The `brs_template_json` defines which `(side, category, is_matched, is_floating)` tuples map to which BRS line. A default template matching the provided YCTMFB template is defined in the appendix.

### 7.4 Dedup hash

```
function compute_dedup_hash(profile_id, side, txn_id_normalized, transaction_date, debit_amount, credit_amount, narration_normalized):
  parts = [
    str(profile_id),
    side,
    txn_id_normalized,
    transaction_date.isoformat(),
    f"{debit_amount:.2f}",
    f"{credit_amount:.2f}",
    sha256(narration_normalized.encode('utf-8')).hexdigest()[:16]
  ]
  joined = "|".join(parts)
  return sha256(joined.encode('utf-8')).hexdigest()
```

Narration is hashed rather than concatenated because narrations are long and the composite key is used as-is.

**Normalization functions:**

```
function normalize_txnid(raw):
  return raw.strip().upper()

function normalize_narration(raw):
  # Uppercase, collapse whitespace, strip trailing/leading
  return re.sub(r'\s+', ' ', raw.strip().upper())
```

### 7.5 Column mapping signature

```
function compute_header_signature(header_row_values):
  normalized = [str(v).strip().lower() for v in header_row_values if v is not None]
  joined = "|".join(normalized)
  return sha256(joined.encode('utf-8')).hexdigest()[:32]
```

On upload, the system reads the header row (as specified by the active mapping's `header_row` field for the profile+side), computes its signature, and compares against known mappings. Exact match → auto-apply. No match → prompt user to create a new mapping version.

### 7.6 Previous-month detection

During classification, a CB transaction is tagged as "previous month" if its narration references a transaction date earlier than the run's `period_start` (e.g., a 30/01 reference in a transaction posted on 02/11). The heuristic:

```
function detect_previous_month(txn, period_start):
  # Look for date patterns in narration
  patterns = [
    r'(\d{1,2})[/\-](\d{1,2})[/\-]?(\d{2,4})?',
    r'(\d{1,2})-(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)-(\d{2,4})'
  ]
  for pattern in patterns:
    matches = re.findall(pattern, txn.narration.upper())
    for m in matches:
      try:
        referenced_date = parse_date_flexible(m)
        if referenced_date < period_start:
          return True
      except ValueError:
        continue
  return False
```

When detected, `source_category = 'previous_month'` is set. These transactions appear in the "Previous Month" informational section of Notes but are excluded from BRS line totals (per the YCTMFB template convention).

---

## 8. Rule builder DSL

Rules are expressed as condition trees serialized as JSON. The frontend renders a visual builder; the backend evaluates the tree directly.

### 8.1 Condition tree schema

```json
{
  "op": "AND" | "OR" | "NOT" | "LEAF",
  "children": [<condition>],
  "field": "narration" | "txnid" | "amount" | "date" | "side" | "dr_cr",
  "operator": "contains" | "not_contains" | "starts_with" | "ends_with" | "equals" | "not_equals" | "matches_regex" | "in_list" | "not_in_list" | "gt" | "gte" | "lt" | "lte" | "between" | "before" | "after" | "on_or_before" | "on_or_after",
  "value": <any>,
  "case_sensitive": false
}
```

A LEAF node has `field`, `operator`, `value` (and optional `case_sensitive` for string operators). A non-LEAF node has `op` (AND/OR/NOT) and `children`. NOT MUST have exactly one child; AND/OR MUST have at least one child.

**Field-operator compatibility:**

| Field | Valid operators |
|---|---|
| `narration` | contains, not_contains, starts_with, ends_with, equals, not_equals, matches_regex |
| `txnid` | contains, not_contains, starts_with, ends_with, equals, not_equals, in_list, not_in_list, matches_regex |
| `amount` | equals, not_equals, gt, gte, lt, lte, between |
| `date` | equals, before, after, on_or_before, on_or_after, between |
| `side` | equals, not_equals |
| `dr_cr` | equals, not_equals |

Values for `between` are `[low, high]` inclusive. Values for `in_list` / `not_in_list` are arrays.

### 8.2 Example conditions

**Stamp duty rule** (corresponds to "Electronic Money Transfer" category):

```json
{
  "op": "LEAF",
  "field": "narration",
  "operator": "starts_with",
  "value": "STAMP DUTY",
  "case_sensitive": false
}
```

**Transfer charges rule:**

```json
{
  "op": "OR",
  "children": [
    {
      "op": "LEAF",
      "field": "narration",
      "operator": "starts_with",
      "value": "COMM - ",
      "case_sensitive": false
    },
    {
      "op": "LEAF",
      "field": "narration",
      "operator": "starts_with",
      "value": "VAT - ",
      "case_sensitive": false
    }
  ]
}
```

**Remita Bulk Credit rule:**

```json
{
  "op": "AND",
  "children": [
    {"op": "LEAF", "field": "narration", "operator": "matches_regex", "value": "^R-\\d+/Bulk Credit", "case_sensitive": false},
    {"op": "LEAF", "field": "amount", "operator": "lt", "value": 20000}
  ]
}
```

### 8.3 Evaluation semantics

```
function evaluate_condition(node, txn):
  if node.op == 'LEAF':
    return evaluate_leaf(node, txn)
  elif node.op == 'AND':
    return all(evaluate_condition(c, txn) for c in node.children)
  elif node.op == 'OR':
    return any(evaluate_condition(c, txn) for c in node.children)
  elif node.op == 'NOT':
    return not evaluate_condition(node.children[0], txn)

function evaluate_leaf(node, txn):
  field_value = get_field_value(txn, node.field)
  if field_value is None: return False
  if node.field in ('narration', 'txnid', 'side', 'dr_cr'):
    if not node.get('case_sensitive', False):
      field_value = str(field_value).upper()
      value = str(node.value).upper() if isinstance(node.value, str) else [str(v).upper() for v in node.value]
    else:
      value = node.value
    return apply_string_op(field_value, node.operator, value)
  elif node.field == 'amount':
    amount = txn.debit_amount + txn.credit_amount
    return apply_numeric_op(amount, node.operator, node.value)
  elif node.field == 'date':
    return apply_date_op(txn.transaction_date, node.operator, node.value)
```

Regex evaluation uses Python's `re` module with `re.IGNORECASE` when `case_sensitive=False`. Regex compilation is cached per rule to avoid recompilation on every transaction.

### 8.4 Visual builder UX contract

The frontend renders the condition tree as nested draggable groups. Each LEAF is a row with three controls: field dropdown, operator dropdown (filtered by field compatibility), value input (type-appropriate). Each non-LEAF group shows the logical operator (AND/OR) as a toggle and an "add condition" button. NOT is a wrapper shown as a "NOT" button applied to a single child.

**Preview endpoint** — `POST /api/profiles/{id}/rules/preview` accepts a condition tree and returns the count of matching transactions in the current profile's un-reconciled ledger. This enables the "X transactions would match" live preview.

### 8.5 Versioning and period freeze

Editing a rule on an ACTIVE ruleset version is NOT permitted. Editing creates a new DRAFT version automatically, cloning all rules. The tenant admin can make further edits on the DRAFT, then activate it — which transitions the previous ACTIVE to FROZEN (if runs reference it) or ARCHIVED (if not) and promotes DRAFT to ACTIVE with `activated_at` stamped.

A run locks its ruleset version at the moment it transitions from DRAFT to CLASSIFYING. Subsequent activation of a newer version does not affect already-running runs.

Period-boundary enforcement: the system SHOULD warn (but not block) a tenant admin who activates a new ruleset version mid-period. The UI presents the current period and suggests activating on the 1st of the next month.

---

## 9. Ingestion pipeline

### 9.1 Upload flow

1. User initiates upload from the UI. Frontend calls `POST /api/profiles/{id}/uploads` with intent metadata (side, expected period).
2. Backend creates an `uploads` row in `RECEIVED` status, generates a presigned R2 URL (PUT, 1-hour expiry), and returns the URL + upload_id.
3. Frontend uploads the file directly to R2 via the presigned URL. On success, frontend calls `POST /api/profiles/{id}/uploads/{upload_id}/commit` to signal completion.
4. Backend verifies the object exists in R2, records `r2_etag`, transitions to `PARSING`, and enqueues a background job.
5. Frontend polls `GET /api/profiles/{id}/uploads/{upload_id}` for status updates.

### 9.2 Parse phase

The background job:

1. Downloads the file from R2 to a temp path on the worker.
2. Opens with `openpyxl` (for .xlsx) or `csv` (for .csv). Streaming mode for .xlsx (`read_only=True`) to handle 100k-row files without loading everything in memory.
3. Reads the header row at `mapping.header_row`. Computes header signature. Attempts to match against known mappings for this (profile, side).
4. If match found and signature is unchanged, proceeds with the matched mapping.
5. If no match: sets `status=FAILED` with error_json indicating "unknown column layout; please configure a column mapping". The user is redirected to the mapping wizard.
6. On matched mapping, streams rows starting at `mapping.data_start_row`. For each row:
   - Apply `skip_if_row_matches` rules; skip if matched.
   - Parse each column per its `parser`. Skip row if required fields are missing or unparseable; accumulate warnings.
   - Normalize txn_id, narration.
   - Compute dedup_hash.
   - Emit parsed row to staging list.
7. Transitions to `PARSED`. Updates `rows_parsed`, `period_covered_start`, `period_covered_end`.

### 9.3 Ingest phase

1. Transitions to `INGESTING`.
2. Bulk-inserts staging rows into `transactions` with `INSERT ... ON DUPLICATE KEY UPDATE id=id` (effective no-op on duplicate) keyed on `dedup_hash`. Batch size: 1000 rows.
3. Counts actual insertions via `ROW_COUNT()` or delta check: new rows have never-before-seen `id`.
4. Populates `uploads.rows_new`, `rows_duplicate`, `rows_rejected`.
5. Transitions to `INGESTED`.
6. Emits audit log entry `UPLOAD_COMPLETED`.

### 9.4 Error handling

Parse errors at the row level do not fail the whole upload; they accumulate in `error_json.warnings` with row numbers. Only parse errors at the file level (unreadable file, missing mapping, corrupted xlsx) fail the upload.

The user-facing error display distinguishes:
- **Upload failed** — whole file couldn't be processed. Actionable: re-upload or fix format.
- **Partial ingest with warnings** — most rows succeeded, some rejected. Shows row numbers and reasons.

### 9.5 Drip-feed overlap handling

A user may upload a statement covering Feb 1-15, then later upload a statement covering Feb 10-28. Overlap rows (Feb 10-15) will have matching dedup hashes and be silently skipped. The `uploads.rows_duplicate` count reflects this.

**Edge case:** if a row's content changes (e.g., bank corrects a narration) the dedup hash will differ, and the "corrected" row will be inserted as a new transaction. This is detected by the matcher if both old and new refer to the same TxnID. A reviewer resolves the duplicate. An explicit "upload correction" workflow is DEFERRED.

### 9.6 Period coverage tracking

Each upload records `period_covered_start` and `period_covered_end` (min and max of transaction dates in the file). This enables the UI to show "Profile X has coverage: BS through Feb 27, CB through Feb 25" before initiating a run, so the preparer knows whether to upload more data.

---

## 10. Starting ledger wizard

Runs once per profile, at initialization. Sets the immutable cutover point.

### 10.1 Inputs

**Step 1 — Cutover date.** User selects a date. All transactions with `transaction_date < cutover_date` are considered pre-existing and out of scope for normal reconciliation. The date is immutable after wizard completion.

**Step 2 — Opening balance.** User provides the GL opening balance and BS opening balance as of the cutover date. Either direct entry or via a small uploaded file with opening balances.

**Step 3 — Floating items (optional).** Upload a file of outstanding items at cutover: transactions on one side that hadn't yet appeared on the other at cutover, and are expected to clear in future periods. Columns: side (BS/CB), date, txnid, narration, debit, credit. These rows are ingested with `is_floating_seed=TRUE`, status `CLASSIFIED` but not `RECONCILED`, so they're available for matching in future runs.

**Step 4 — Reconciled history (optional).** Upload a file of historical transactions that were already reconciled before cutover. Same schema as floating items but with an additional column `reconciled_in_period` (for audit reference). These rows are ingested with `is_floating_seed=TRUE`, status `RECONCILED`, so they serve only as dedup guards against future uploads that overlap pre-cutover dates.

**Step 5 — Confirmation.** User reviews a summary: cutover date, opening balances, floating item count by side, reconciled history count. Must type the profile's code to confirm. Wizard locks the profile (`profiles.cutover_date` set, `status` → `INITIALIZED`).

### 10.2 Validation

- Cutover date MUST not be in the future.
- Opening balances MUST be non-zero Decimal.
- Floating items MUST have transaction_date strictly less than cutover_date.
- Reconciled history MUST have transaction_date strictly less than cutover_date.
- Total debits + credits on floating items MUST not exceed 10% of opening balance (sanity check; warning only, can be overridden).

### 10.3 Post-wizard behavior

Subsequent uploads reject any row with `transaction_date < cutover_date` as "pre-cutover, ignored" (with a warning in upload summary). This prevents accidental re-ingest of historical data.

---

## 11. Run workflow

### 11.1 Initiating a run

Preparer on the profile navigates to "New Run", selects a period (`period_start`, `period_end`). Period defaults: start = day after the previous APPROVED run's `period_end`, or `cutover_date` if no prior run; end = today or end-of-month.

Pre-flight checks:
- No existing non-SUPERSEDED run for (profile, overlapping period). If an existing run overlaps, the UI offers: (a) cancel, (b) extend the existing run, (c) supersede the existing run (requires tenant admin).
- Profile has at least one ACTIVE ruleset version.
- Profile has ACTIVE column mappings for both BS and CB sides.
- Opening balances are set (from carry-forward or explicit).

Backend creates the `runs` row in DRAFT, assigns `preparer_user_id`, sets `ruleset_version_id` to the currently ACTIVE version.

### 11.2 Scope selection

On transitioning DRAFT → CLASSIFYING, the backend identifies in-scope transactions:

```sql
SELECT * FROM transactions
WHERE profile_id = :profile_id
  AND transaction_date BETWEEN :period_start AND :period_end
  AND status NOT IN ('RECONCILED', 'EXCLUDED')
```

Plus floating items that are still un-matched (from starting ledger or prior periods):

```sql
SELECT * FROM transactions
WHERE profile_id = :profile_id
  AND is_floating_seed = TRUE
  AND status NOT IN ('RECONCILED', 'EXCLUDED')
  AND transaction_date < :period_start
```

All in-scope transactions are updated: `run_id = :run.id`, `status = PENDING`.

### 11.3 Classification phase

See Section 7.1. Runs as background job. On completion, transitions CLASSIFYING → MATCHING.

### 11.4 Matching phase

See Section 7.2. Runs as background job. On completion, computes BRS totals via Section 7.3, persists to `runs.computed_totals_json`, transitions MATCHING → REVIEW_READY.

### 11.5 Preparer review

The preparer UI shows:

- **Overview:** BRS preview (current totals), counts per bucket (confident/variance/review/unmatched per side).
- **Review queue:** list of `match_records` with `bucket=REVIEW`, sortable by score DESC. Each row shows both transactions side-by-side with highlighted differences.
- **Variance queue:** list with `bucket=VARIANCE`.
- **Unmatched lists:** BS and CB unmatched transactions, with a "find match" search box.

Preparer actions per match record:
- Accept — move to ACCEPTED; transaction statuses to MATCHED/VARIANCE_MATCHED.
- Reject — move to REJECTED; transactions return to UNMATCHED.
- Manually pair — select a BS and CB transaction from unmatched lists; create an ACCEPTED match record with `score=1.0` (manual) and reviewer_disposition recorded.

Preparer must clear the REVIEW bucket (zero unresolved) before submitting. VARIANCE items may be left for the reviewer.

On submission: preparer clicks "Submit for Review", is prompted for confirmation + password re-entry (not MFA — just a sanity step), backend writes a `signing_records` row (role=PREPARER), transitions REVIEW_READY → UNDER_REVIEW, emails the reviewer.

### 11.6 Reviewer review

Reviewer UI is similar to preparer's but shows the preparer's dispositions as context. Reviewer can:
- Confirm preparer's dispositions (bulk or individually).
- Override preparer's dispositions (logged in audit).
- Dispose of VARIANCE items: accept (variance flows to BRS as difference line), reject (both sides unmatched).
- Return the run to preparer with a note.

Reviewer must clear all VARIANCE items before submitting. On submission: writes `signing_records` row (role=REVIEWER), transitions to APPROVAL_READY, emails approver.

### 11.7 Approver review

Approver UI is read-only except for the approve/return buttons. Shows the full BRS preview, Notes preview, signing history to date. Approver can:
- Approve — writes `signing_records` (role=APPROVER); transitions to APPROVED; triggers final reconciliation of all in-run transactions to `RECONCILED`; ruleset version is frozen; transitions to PUBLISHED immediately.
- Return to reviewer — with a note; transitions back to UNDER_REVIEW.

### 11.8 Post-approval

Once PUBLISHED, the run is immutable:
- Outputs (BRS.xlsx, Notes.xlsx, PDF) renderable on demand.
- Match records, transaction statuses, signing records — all frozen.
- No further state changes except SUPERSEDE (by tenant admin).

**Supersede:** a tenant admin can create a new run for the same period if corrections are needed. The new run is created in DRAFT with the same period. The old run transitions to SUPERSEDED, `superseded_by_run_id` points to the new run. All previously-reconciled transactions from the old run revert to their pre-reconciliation status in scope of the new run. The audit trail preserves the full history.

### 11.9 Notifications

Email notifications (via SES) sent on:
- Run submitted for review → reviewer(s)
- Run submitted for approval → approver(s)
- Run returned to preparer/reviewer → previous actor
- Run approved → preparer + reviewer + tenant admins
- Run superseded → all prior actors

Notification templates: subject, body, link to the run. DEFERRED: notification preferences per user. v1: all relevant users notified.

---

## 12. Outputs

All outputs render on demand from DB state. No pre-rendered artefacts are stored.

### 12.1 BRS.xlsx

Mirrors the template's structure:

- Row 1-4: Header (tenant name, address, BRS title with period end date).
- Row 5: Bank name cell.
- Row 6: Currency headers ("N" and "N").
- Rows 7 onward: the reconciliation lines per Section 7.3.
- Final rows: signature block populated from signing_records.

Uses openpyxl with:
- Formulas for subtotals (e.g., `=B9+B10+B11` for total credits), so the file is navigable and auditable.
- Cell comments on key cells documenting data provenance (e.g., "Source: Run #123, computed 2026-02-28 14:32 UTC").
- Number format `#,##0.00;(#,##0.00);-` for all money columns.
- Borders, bold totals, and font (Arial 11) matching the template.

### 12.2 Notes.xlsx

Two-column layout mirroring the template. Sections:

- Recurrent Bank Charges (Electronic Money Transfer + Account Maintenance Charge side-by-side)
- Transfer Charges (single column)
- Remita Wallet Top-up + Remita Bulk Credit (side-by-side)
- Debit Transactions in Cash Book (Current Month) + Credit Transactions in Cash Book (side-by-side)
- Debit Transaction in Bank Statement + Credit Transaction in Bank Statement (side-by-side)
- Debit Transactions in Cash Book (Previous Month) — informational, full-width

Each section has columns: Transaction Date, Transaction ID, Narration, Amount, with a subtotal row. Rows are sourced from transactions filtered by (side, category) and sorted by transaction_date.

### 12.3 Signed PDF

Renders both BRS and Notes as a single PDF. Uses a templating engine (WeasyPrint recommended — HTML/CSS to PDF, good for tabular data). Signature block includes full names, titles, signed_at timestamps from `signing_records`. Page footer includes: tenant name, run ID, generated-at timestamp, page number.

PDF is digitally signed (PDF signature) using a tenant-level signing key held in secrets. DEFERRED for v1: use a visual signature block only; real digital signing in v2.

### 12.4 Reproducibility

Every output is a pure function of `(run_id, output_type)`. Calling the endpoint twice produces byte-identical files (modulo a deterministic generation timestamp). This is testable.

### 12.5 Output endpoints

- `GET /api/runs/{id}/outputs/brs.xlsx` — streams the file
- `GET /api/runs/{id}/outputs/notes.xlsx` — streams the file
- `GET /api/runs/{id}/outputs/signed.pdf` — streams the file
- `GET /api/runs/{id}/outputs/audit-trail.json` — structured audit dump for external auditors

All require the user to have access to the run (preparer, reviewer, approver, or tenant admin).

### 12.6 Retention

Generated files are NOT persisted. They are rendered on demand. The underlying data is retained per the tenant data retention policy (indefinite for transactions, runs, audit logs; 180-day retention on raw upload blobs in R2).

---

## 13. Authentication and tenancy flow

### 13.1 Login flow (normal user)

1. User navigates to `https://app.com/login`.
2. Enters email and password.
3. POST `/auth/login` → platform backend:
   - Lookup `user_directory` row by email.
   - Verify password hash (argon2).
   - Check status is ACTIVE (reject LOCKED, DISABLED, PENDING).
   - Increment failed_login_count on mismatch; lock account if exceeds threshold (default 5, locked for 15 min).
4. If MFA is not enrolled and policy permits (OPTIONAL tier, or non-admin user in REQUIRED_FOR_ADMINS tier):
   - Issue a handoff token directly; skip to step 7.
5. If MFA is enrolled:
   - Issue a pre-auth token (Redis, 5-min TTL).
   - Response: `{next: "mfa_required", preauth_token: "..."}`.
   - Frontend shows MFA input.
   - POST `/auth/mfa/verify` with pre-auth token and TOTP code.
   - Verify TOTP against encrypted secret (with ±1 time-step window).
   - On success, consume pre-auth token, issue handoff token.
6. If MFA is required but not enrolled (policy-forced for this user):
   - Issue an MFA enrollment token.
   - Response: `{next: "mfa_enrollment_required", enrollment_token: "..."}`.
   - Frontend shows QR + enrollment flow.
   - On successful enrollment (validated first TOTP), transition to step 7.
7. Issue handoff token (Redis, 30-second TTL), bound to `(user_directory_id, tenant_id, mfa_verified=true/false)`.
8. Response: `{next: "redirect", redirect_url: "https://{tenant.slug}.app.com/auth/handoff?token={handoff_token}"}`.
9. Frontend performs browser redirect (`window.location.href`).
10. Tenant subdomain receives handoff request:
    - GET `/auth/handoff?token=...`.
    - Backend consumes handoff token from Redis (atomic delete-on-read).
    - Validates `tenant_id` matches subdomain's tenant.
    - Loads tenant DB; finds user row.
    - Issues access token (JWT, 15-min TTL) and refresh token (opaque, 7-day TTL, stored in `auth_sessions`).
    - Sets cookies scoped to `{tenant.slug}.app.com`: `access_token` (HttpOnly, Secure, SameSite=Strict), `refresh_token` (HttpOnly, Secure, SameSite=Strict).
    - Redirects to `/` (tenant dashboard).

### 13.2 JWT claims

```json
{
  "iss": "app.com",
  "sub": "user_directory_id",
  "aud": "{tenant.slug}.app.com",
  "tenant_id": 123,
  "tenant_slug": "yctmfb",
  "tenant_user_id": 456,
  "roles": ["PREPARER"],
  "is_tenant_admin": false,
  "mfa_verified": true,
  "iat": 1719000000,
  "exp": 1719000900
}
```

Signed with RS256 using a platform signing key. Public key served at `/.well-known/jwks.json` so frontend and tenant subdomain can verify without DB lookups.

Backend middleware on tenant subdomains MUST validate: signature, expiry, `tenant_slug` matches subdomain's tenant, `tenant_id` exists and is ACTIVE.

### 13.3 Refresh flow

Access token expires after 15 minutes. Before expiry, frontend calls `POST /auth/refresh` with refresh token cookie. Backend:
- Looks up `auth_sessions` by refresh_token_hash.
- Rejects if revoked or expired.
- Atomically: create new session, mark old as rotated_from, issue new tokens.
- Sets new cookies.

If a revoked refresh token is presented, the backend invalidates all sessions for that user (defensive reaction to potential token theft) and requires re-login.

### 13.4 Logout

`POST /auth/logout` — revokes the current `auth_sessions` row, clears cookies. Does not invalidate the access token (short TTL; JWT is stateless). "Logout everywhere" revokes all sessions for the user.

### 13.5 Password reset

1. User at `app.com/forgot-password` enters email.
2. Backend looks up `user_directory`. If exists, generates a reset token (32-byte random, stored hashed in Redis with 1-hour TTL), sends email via SES with link `https://app.com/reset-password?token={token}`. If not exists, still returns 200 (no email enumeration leak).
3. User clicks link, enters new password.
4. Backend validates token (hash lookup, single-use, atomic consume), validates password (min 12 chars, passes basic complexity), updates `password_hash`, stamps `password_changed_at`, revokes all existing sessions.
5. Redirects to login.

Password reset does NOT bypass MFA. After reset, user still goes through the normal login flow including MFA.

### 13.6 MFA enrollment

1. User initiates from `/settings/security` (tenant subdomain).
2. Backend generates a 160-bit secret, stores encrypted, returns provisioning URI: `otpauth://totp/{tenant.slug}:{user.email}?secret={base32}&issuer={tenant.display_name}&period=30&digits=6&algorithm=SHA1`.
3. Frontend renders QR code using the URI.
4. User scans with authenticator app, enters first TOTP code.
5. Backend validates code; if valid, sets `mfa_enabled=TRUE`, `mfa_enrolled_at=now`.
6. Backend generates 10 backup codes (single-use, 8 chars each, hashed before storage). Shown to user ONCE; user must confirm they've saved them before continuing.
7. Subsequent logins require TOTP.

**MFA reset:** if user loses authenticator, tenant admin can reset MFA via admin console. Logs `MFA_POLICY_CHANGED` event. User must re-enroll at next login. This action is NOT available to the user themselves.

### 13.7 MFA enforcement tiers

Per-tenant setting stored in `mfa_policy`:

- `OPTIONAL` — users choose whether to enable MFA. Login without MFA is permitted even if enrolled.
- `REQUIRED_FOR_ADMINS` — tenant admins, approvers MUST enable MFA. Others optional.
- `REQUIRED_FOR_ALL` — all users MUST enable MFA.

Changing the tier immediately affects subsequent logins. Users affected by a tightened policy are redirected to the enrollment flow at next login and cannot proceed until complete.

### 13.8 Session handling on handoff

When a user is already logged into Tenant A and attempts to log into Tenant B (different email tied to Tenant B), the flow is: handoff to Tenant B sets cookies on Tenant B's subdomain; Tenant A's cookies on Tenant A's subdomain are untouched. The two sessions are fully independent. User can have both open simultaneously in different tabs.

### 13.9 Invitation flow

1. Tenant admin at `yctmfb.app.com/users/invite` enters invitee's email and role(s).
2. Backend creates:
   - Tenant DB: `users` row with status INVITED.
   - Platform DB: `user_directory` row with status PENDING, random temporary `password_hash`, tenant_id set, tenant_user_id set.
   - Invitation token (Redis, 48-hour TTL) bound to user_directory_id.
3. Email sent via SES with link `https://app.com/accept-invitation?token={token}`.
4. Invitee clicks link, sets password, completes MFA enrollment (if required by tier).
5. Both records transition to ACTIVE.

Invitation token expires after 48 hours. Tenant admin can resend invitation (new token, old invalidated).

### 13.10 Platform admin login

Separate from tenant user login. Served at `platform.app.com/login` or `app.com/platform/login`. Distinct `platform_admins` table. MFA is MANDATORY (cannot be disabled). No tenant context; sessions are scoped to the platform subdomain. Direct redirect to platform admin dashboard on success.

---

## 14. API surface

### 14.1 Conventions

All endpoints return JSON. Errors follow the shape:

```json
{
  "error": {
    "code": "INVALID_STATE_TRANSITION",
    "message": "Cannot submit a run in state DRAFT for approval.",
    "details": {"current_state": "DRAFT", "attempted_event": "SUBMIT_FOR_APPROVAL"}
  }
}
```

HTTP status codes:
- 200 OK for reads and successful actions with a response body.
- 201 Created for resource creation.
- 204 No Content for actions without a response body.
- 400 Bad Request for validation errors.
- 401 Unauthorized for missing/invalid auth.
- 403 Forbidden for authenticated but not authorized.
- 404 Not Found.
- 409 Conflict for state-machine violations or uniqueness violations.
- 422 Unprocessable Entity for business-rule violations.
- 429 Too Many Requests for rate limiting (DEFERRED but endpoint responds cleanly).
- 500 Internal Server Error for bugs.

All timestamps in responses are ISO 8601 with UTC offset. All decimals are serialized as strings to preserve precision: `"amount": "1000000.00"`.

Pagination: cursor-based. Query params: `limit` (default 50, max 200), `cursor` (opaque string from previous response). Response includes `next_cursor` (null if end).

### 14.2 Platform API (`/platform/*`)

Requires platform admin session.

- `POST /platform/tenants` — create tenant. Body: `{slug, display_name, admin_email, admin_full_name, plan}`. Response: tenant row.
- `GET /platform/tenants` — list tenants with pagination and status filter.
- `GET /platform/tenants/{id}` — tenant detail.
- `PATCH /platform/tenants/{id}` — update plan, limits, display_name.
- `POST /platform/tenants/{id}/suspend` — transition to SUSPENDED.
- `POST /platform/tenants/{id}/activate` — transition from SUSPENDED back to ACTIVE.
- `POST /platform/tenants/{id}/schedule-deletion` — transition to SCHEDULED_FOR_DELETION.
- `POST /platform/tenants/{id}/cancel-deletion` — cancel scheduled deletion.
- `POST /platform/tenants/{id}/export` — trigger a mysqldump job; DEFERRED beyond schema stub.
- `GET /platform/audit-log` — paginated platform audit log.

### 14.3 Auth API (`/auth/*`)

Public, no auth required. Rate limited.

- `POST /auth/login` — `{email, password}` → handoff or pre-auth token.
- `POST /auth/mfa/verify` — `{preauth_token, totp_code}` → handoff token.
- `POST /auth/mfa/backup-code` — `{preauth_token, backup_code}` → handoff token (consumes backup code).
- `POST /auth/mfa/enroll` — tenant-scoped, requires session. Returns provisioning URI + QR image.
- `POST /auth/mfa/enroll/confirm` — `{totp_code}` → confirms enrollment, returns backup codes.
- `POST /auth/refresh` — refresh token in cookie → new token pair.
- `POST /auth/logout` — revokes current session.
- `POST /auth/logout-everywhere` — revokes all sessions for user.
- `POST /auth/forgot-password` — `{email}` → always 200.
- `POST /auth/reset-password` — `{token, new_password}` → 204.
- `POST /auth/accept-invitation` — `{token, password}` → activates account.
- `GET /auth/handoff` — validates handoff token, sets cookies, redirects.
- `GET /.well-known/jwks.json` — public keys for JWT verification.

### 14.4 Tenant API (`/api/*`)

Requires tenant session.

**Users and roles:**
- `GET /api/users` — list tenant users.
- `POST /api/users/invite` — invite user. Requires tenant admin.
- `PATCH /api/users/{id}` — update user (name, title). Self or tenant admin.
- `POST /api/users/{id}/suspend` — tenant admin only.
- `POST /api/users/{id}/reset-mfa` — tenant admin only.
- `GET /api/users/{id}/roles` — list role assignments.
- `POST /api/users/{id}/roles` — assign role. Body: `{profile_id, role}`. Tenant admin only.
- `DELETE /api/users/{id}/roles/{assignment_id}` — revoke role. Tenant admin only.

**Tenant settings:**
- `GET /api/tenant/settings` — MFA policy, branding (DEFERRED).
- `PATCH /api/tenant/settings` — update settings. Tenant admin only.

**Profiles:**
- `GET /api/profiles` — list profiles.
- `POST /api/profiles` — create profile (DRAFT status). Tenant admin only.
- `GET /api/profiles/{id}` — detail.
- `PATCH /api/profiles/{id}` — update profile metadata. Tenant admin only.
- `POST /api/profiles/{id}/starting-ledger/wizard` — initiate wizard.
- `POST /api/profiles/{id}/starting-ledger/complete` — finalize wizard.

**Column mappings:**
- `GET /api/profiles/{id}/column-mappings` — list versions.
- `POST /api/profiles/{id}/column-mappings` — create new version. Body: mapping_json.
- `POST /api/profiles/{id}/column-mappings/detect` — upload a file, return header signature and suggested mapping.

**Rules:**
- `GET /api/profiles/{id}/rulesets` — list versions.
- `POST /api/profiles/{id}/rulesets` — create draft version.
- `GET /api/profiles/{id}/rulesets/{version_id}/rules` — list rules.
- `POST /api/profiles/{id}/rulesets/{version_id}/rules` — create rule.
- `PATCH /api/profiles/{id}/rulesets/{version_id}/rules/{rule_id}` — update rule (draft only).
- `DELETE /api/profiles/{id}/rulesets/{version_id}/rules/{rule_id}` — delete rule (draft only).
- `POST /api/profiles/{id}/rulesets/{version_id}/activate` — activate draft.
- `POST /api/profiles/{id}/rules/preview` — preview how many txns match a condition tree.

**Uploads:**
- `POST /api/profiles/{id}/uploads` — start upload, returns presigned URL + upload_id.
- `POST /api/profiles/{id}/uploads/{upload_id}/commit` — signal R2 upload complete.
- `GET /api/profiles/{id}/uploads/{upload_id}` — upload status.
- `GET /api/profiles/{id}/uploads` — list uploads with filters.

**Transactions (read-only for users):**
- `GET /api/profiles/{id}/transactions` — paginated, filterable (side, date range, status, category).
- `GET /api/profiles/{id}/transactions/{txn_id}` — detail.

**Runs:**
- `POST /api/profiles/{id}/runs` — create DRAFT run. Body: `{period_start, period_end}`.
- `GET /api/profiles/{id}/runs` — list.
- `GET /api/profiles/{id}/runs/{run_id}` — detail with computed totals.
- `POST /api/profiles/{id}/runs/{run_id}/run-classification` — transition DRAFT → CLASSIFYING.
- `POST /api/profiles/{id}/runs/{run_id}/submit-for-review` — preparer action.
- `POST /api/profiles/{id}/runs/{run_id}/return-to-preparer` — reviewer action.
- `POST /api/profiles/{id}/runs/{run_id}/submit-for-approval` — reviewer action.
- `POST /api/profiles/{id}/runs/{run_id}/return-to-reviewer` — approver action.
- `POST /api/profiles/{id}/runs/{run_id}/approve` — approver action.
- `POST /api/profiles/{id}/runs/{run_id}/supersede` — tenant admin action.

**Match records:**
- `GET /api/runs/{run_id}/matches` — list, filterable by bucket.
- `POST /api/runs/{run_id}/matches/{match_id}/accept` — disposition.
- `POST /api/runs/{run_id}/matches/{match_id}/reject` — disposition.
- `POST /api/runs/{run_id}/manual-match` — create manual match. Body: `{bs_transaction_id, cb_transaction_id, note}`.

**Outputs:**
- `GET /api/runs/{run_id}/outputs/brs.xlsx`
- `GET /api/runs/{run_id}/outputs/notes.xlsx`
- `GET /api/runs/{run_id}/outputs/signed.pdf`
- `GET /api/runs/{run_id}/outputs/audit-trail.json`

**Audit log:**
- `GET /api/audit-log` — paginated, filterable by event_type, target, actor, date range. Visible to tenant admins.

### 14.5 Pydantic model examples

`UserResponse`:

```python
class UserResponse(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    title: Optional[str]
    is_tenant_admin: bool
    status: Literal['INVITED', 'ACTIVE', 'SUSPENDED']
    created_at: datetime
    roles: List[RoleAssignmentResponse]
```

`RuleCreateRequest`:

```python
class RuleCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    priority: int = Field(ge=0, le=10000)
    side: Literal['BS', 'CB', 'BOTH']
    dr_cr: Literal['DEBIT', 'CREDIT', 'ANY']
    condition: ConditionNode  # recursive Pydantic model for condition tree
    target_category: str = Field(min_length=1, max_length=64)
    is_enabled: bool = True

class ConditionNode(BaseModel):
    op: Literal['AND', 'OR', 'NOT', 'LEAF']
    children: Optional[List['ConditionNode']] = None
    field: Optional[Literal['narration', 'txnid', 'amount', 'date', 'side', 'dr_cr']] = None
    operator: Optional[str] = None
    value: Optional[Any] = None
    case_sensitive: bool = False

    @model_validator(mode='after')
    def validate_shape(self):
        # LEAF must have field/operator/value; AND/OR must have children; NOT must have one child
        ...
```

`RunStateTransitionRequest`:

```python
class RunStateTransitionRequest(BaseModel):
    note: Optional[str] = Field(default=None, max_length=2048)
    password_confirmation: Optional[str] = None  # For signing actions
```

---

## 15. Frontend architecture

### 15.1 Stack

- **Framework:** Next.js 14+ with App Router.
- **Language:** TypeScript 5+, strict mode.
- **Styling:** Tailwind CSS with a design token layer in `tailwind.config.ts`.
- **Component primitives:** shadcn/ui (copy-in components, owned by the project).
- **Forms:** React Hook Form + Zod for validation. Zod schemas are the single source of truth for TypeScript types + runtime validation.
- **Server state:** TanStack Query (React Query) v5.
- **Client state:** Zustand for cross-page state; React Context for auth.
- **Tables:** TanStack Table (headless) + TanStack Virtual for virtualized rendering of large lists.
- **Charts:** Recharts for the dashboard (DEFERRED beyond simple totals).
- **Dates:** `date-fns` for formatting and parsing.
- **HTTP:** native `fetch` wrapped in a typed client generated from backend OpenAPI schema.

### 15.2 Deployment topology

Two separate Next.js deployments:
- **Auth shell** on `app.com` (or `auth.app.com`). Pages: login, MFA, forgot-password, reset-password, accept-invitation, handoff receiver.
- **Tenant app** on `*.app.com` (wildcard). Pages: dashboard, profiles, runs, uploads, settings.

Wildcard TLS and DNS are infrastructure concerns (out of scope per your instruction), but the frontend is built assuming this topology.

### 15.3 Route structure (tenant app)

```
app/
├── (auth)/
│   ├── handoff/page.tsx       # Receives handoff token, establishes session
│   └── logout/page.tsx
├── (dashboard)/
│   ├── layout.tsx             # Nav shell, auth guard
│   ├── page.tsx               # Dashboard home
│   ├── profiles/
│   │   ├── page.tsx           # List profiles
│   │   ├── [id]/
│   │   │   ├── page.tsx       # Profile overview
│   │   │   ├── settings/page.tsx
│   │   │   ├── rules/page.tsx  # Rule builder
│   │   │   ├── mappings/page.tsx
│   │   │   ├── uploads/page.tsx
│   │   │   ├── transactions/page.tsx
│   │   │   ├── starting-ledger/page.tsx
│   │   │   └── runs/
│   │   │       ├── page.tsx
│   │   │       └── [run_id]/
│   │   │           ├── page.tsx        # Overview + BRS preview
│   │   │           ├── review/page.tsx # Match queue
│   │   │           └── outputs/page.tsx
│   ├── users/page.tsx         # Tenant admin only
│   ├── audit/page.tsx         # Audit log viewer
│   └── settings/
│       ├── security/page.tsx  # MFA enrollment
│       └── tenant/page.tsx    # Tenant admin only
└── api/                       # Next.js API routes only for BFF concerns (rarely used)
```

### 15.4 Auth guard

A root layout `(dashboard)/layout.tsx` checks for valid session via a server-side call. On 401, redirects to `https://app.com/login?return_to={current_url}`. On expired access token, transparently calls `/auth/refresh`; on failure, full redirect.

### 15.5 API client

Generate TypeScript types from backend OpenAPI schema via `openapi-typescript`. Wrap `fetch` in a typed helper:

```ts
export async function apiCall<T>(
  endpoint: keyof ApiEndpoints,
  options: RequestOptions
): Promise<T> { ... }
```

All React Query hooks are co-located with their endpoint: `useRun(runId)`, `useCreateRun()`, etc.

### 15.6 Key UI components

- **RuleBuilder** — recursive visual editor for condition trees. Each node is draggable. Each leaf is an inline row.
- **MatchReviewQueue** — virtualized list of match records. Each item is an expandable row showing BS and CB transactions side-by-side with score breakdown.
- **TransactionTable** — paginated, filterable, sortable table of transactions.
- **UploadDropzone** — drag-and-drop with progress bar; handles presigned-URL upload.
- **BRSPreview** — renders the computed BRS totals as the BRS looks in the final output.
- **ColumnMappingWizard** — multi-step wizard: upload sample, preview rows, drag fields to columns, test parse, save.
- **StartingLedgerWizard** — multi-step flow matching Section 10.
- **StateMachineBadge** — renders a run's state with color and a tooltip showing valid next transitions.

### 15.7 Accessibility

Target WCAG 2.1 AA. Use shadcn/ui's accessible primitives. All forms have labels. All interactive elements keyboard-navigable. All color contrasts meet AA. Screen reader tested.

### 15.8 Internationalization

DEFERRED. All UI copy in English (Nigerian English), naira symbols. Structured so that `next-intl` can be added later without refactoring.

---

## 16. Testing expectations

### 16.1 Backend unit tests

- **Classification engine:** test every operator in the DSL against synthetic transactions. Test each rule pattern from the appendix. Test fallback behavior when no rule matches.
- **Matching engine:** test each subscore function with edge cases (zero amount, exact dates, max-distance dates, empty narrations, identical txnids). Test weighted combination. Test sign-polarity rejection. Test unique-assignment resolution with multiple candidates.
- **BRS composition:** test each bucket extraction. Test with zero transactions. Test with only credits. Test with only debits. Test precision preservation through Decimal arithmetic.
- **Dedup hash:** test that equivalent transactions produce identical hashes; test that semantically different transactions produce different hashes.
- **State machines:** for each state machine, test every legal transition; test that every illegal transition is rejected with correct error. Parameterize over states + events.
- **Rule condition tree:** test AND/OR/NOT evaluation. Test deeply nested trees. Test short-circuit evaluation.
- **Normalization:** test txnid/narration normalization with unicode, whitespace, mixed case.

### 16.2 Backend integration tests

- **End-to-end reconciliation against the provided template:** ingest the WEMA sheet as BS, the YCTMFB sheet as CB, apply the default ruleset derived from the appendix, run matching with default thresholds, compose BRS. Assert that computed totals match the template's BRS line totals EXACTLY:
  - Closing Balance as per GL: 207,078,584.61
  - Credit Transactions in BS: 30,022,077.79
  - Remita Bulk Credit: 16,000.00
  - Debit Transactions in BS: 200,000,000.00
  - Remita Wallet Top-up & Charges: 3,000,150.00
  - Debit Transactions in CB: 3,511,028.71
  - Account Maintenance Charge: 3,225.38
  - Electronic Money Transfer: 250.00
  - Transfer Charges: 215.00
  - GL Adjusted Balance: 30,601,793.31
  - BS Closing Balance: 49,131,551.32
  - Difference: 18,529,758.01

  This is the acceptance test. If these numbers don't reproduce, the implementation is broken.

- **Tenant provisioning:** create a tenant, verify DB exists, verify seeded rows, verify rollback on failure.
- **Dedup on overlapping upload:** upload same file twice, verify second upload produces zero new rows.
- **Auth flow end-to-end:** register, login, MFA enroll, MFA login, token refresh, logout.

### 16.3 Backend test fixtures

- `fixtures/wema_feb2026.xlsx` — the BS sheet from the provided template.
- `fixtures/yctmfb_feb2026.xlsx` — the CB sheet from the provided template.
- `fixtures/default_ruleset.json` — the appendix-defined starter ruleset.
- `fixtures/expected_brs_totals.json` — the ground-truth numbers above.

### 16.4 Frontend tests

- **Component tests** (Vitest + React Testing Library): RuleBuilder (add/remove/reorder nodes, validate shape), MatchReviewQueue (accept/reject actions), forms (validation errors).
- **Integration tests** (Playwright): login → handoff → dashboard; create profile → upload → run → approve flow.
- v1: DEFERRED but Playwright scaffolding SHOULD be in place.

### 16.5 Test coverage target

Backend: ≥ 80% line coverage on `app/` excluding generated code. Critical paths (classification, matching, state machines, auth) target ≥ 95%.

Frontend: ≥ 60% line coverage (lower bar due to Playwright for the high-value flows).

### 16.6 Mutation testing

DEFERRED. Recommend `mutmut` against the matching and classification engines in v2.

---

## 17. Build order

The sequence below is optimized for AI-assisted implementation. Each stage has acceptance criteria. Do not skip ahead; each stage depends on the previous.

### Stage 1 — Foundation

1. Repository setup: monorepo with `backend/` (FastAPI) and `frontend/` (Next.js) directories.
2. Python environment: `uv` or `poetry`, FastAPI, SQLAlchemy 2.0+, Alembic, Pydantic v2, pytest.
3. Node environment: Next.js 14+, TypeScript strict, Tailwind, shadcn/ui initialized.
4. Dockerfile for backend (multi-stage build). Dockerfile for frontend.
5. `docker-compose.yml` for local development: MySQL 8, Redis 7, app containers.
6. Basic CI: lint + typecheck + unit tests on PR.

**Acceptance:** `docker-compose up` starts all services. `curl http://localhost:8000/health` returns 200. `npm run dev` in frontend shows a placeholder page.

### Stage 2 — Platform database and tenant provisioning

1. Platform DB models (Section 4): `tenants`, `user_directory`, `platform_admins`, `platform_audit_log`, `auth_sessions`, `mfa_backup_codes`.
2. Platform Alembic chain with initial migration.
3. `TenantProvisioner` service with full rollback on failure.
4. Tenant DB models (Section 5 subset: `users`, `mfa_policy`, `audit_log` — enough to seed).
5. Tenant Alembic chain with initial migration.
6. `TenantContextMiddleware` — resolve tenant from subdomain, bind session.
7. Platform admin seed script.

**Acceptance:** Platform admin can create a tenant via a CLI or API call. Tenant DB is created with seeded users table. Dropping the tenant drops the database cleanly.

### Stage 3 — Authentication

1. Argon2id password hashing.
2. Login endpoint (`POST /auth/login`).
3. Pre-auth token + MFA verification (`POST /auth/mfa/verify`).
4. Handoff token issuance and consumption.
5. Access + refresh token issuance and refresh flow.
6. Password reset flow.
7. MFA enrollment flow.
8. Invitation flow.
9. Tenant admin: invite user, assign role (role_assignments table now needed), MFA policy management.

**Acceptance:** End-to-end login with MFA works: start at `app.com/login`, end authenticated on `{slug}.app.com`. All scenarios in Section 13 pass.

### Stage 4 — Profiles and column mappings

1. Tenant DB models: `profiles`, `column_mappings`.
2. Profile CRUD endpoints.
3. Column mapping detection: upload a sample file, compute signature, return suggested field mapping.
4. Column mapping save/version.
5. Frontend: profile list, profile detail, column mapping wizard UI.

**Acceptance:** Tenant admin creates a profile; uploads a sample WEMA statement; maps fields; saves mapping.

### Stage 5 — Rule-set and rule builder

1. Tenant DB models: `ruleset_versions`, `rules`.
2. Rule CRUD endpoints.
3. Condition tree validator (Pydantic models).
4. Rule evaluation function.
5. Rule preview endpoint.
6. Version activation flow.
7. Frontend: visual rule builder, preview pane.

**Acceptance:** Tenant admin creates a ruleset, adds the default rules from the appendix, activates it. Preview shows expected counts against a sample dataset.

### Stage 6 — Ingestion pipeline

1. R2 client wrapper with presigned URL generation.
2. Upload CRUD endpoints.
3. Dramatiq + Redis setup for background jobs.
4. Parse job: streaming openpyxl, apply mapping, normalize, compute dedup hash.
5. Ingest job: bulk insert with dedup.
6. Transactions table created.
7. Frontend: upload dropzone, upload status polling.

**Acceptance:** Upload the template's WEMA sheet; verify all 88 rows ingested. Re-upload the same file; verify 0 new rows. Upload a modified version; verify only changed rows are added.

### Stage 7 — Starting ledger wizard

1. Wizard state tracking (per profile, session-scoped).
2. Opening balance entry.
3. Floating items upload + validation.
4. Reconciled history upload + validation.
5. Wizard finalization: atomic set of cutover_date + opening_balance + seeded transactions.
6. Frontend: multi-step wizard UI.

**Acceptance:** Complete the wizard for a fresh profile. Verify cutover_date is immutable. Verify floating items are ingested with `is_floating_seed=TRUE`.

### Stage 8 — Classification engine

1. Classification function (Section 7.1).
2. Previous-month detection.
3. Category assignment to transactions.
4. Background job wrapper.

**Acceptance:** Given the template's transactions and the default ruleset, verify that:
- All 5 stamp duty transactions are categorized as "Electronic Money Transfer"
- Both AMC entries as "Account Maintenance Charge"
- All COMM and VAT entries as "Transfer Charges"
- The two Remita Wallet Top-up entries as "Remita Wallet Top-up"

### Stage 9 — Matching engine

1. Candidate generation with indexed pre-filter.
2. Subscore functions.
3. Weighted scoring.
4. Sign-polarity check.
5. Bucket assignment.
6. Unique-assignment resolution.
7. Match record materialization.
8. Transaction status updates.
9. Background job wrapper.

**Acceptance:** Running the matcher against the template data produces match records that correspond to the same-TxnID items the template implicitly matches. The ₦600 discrepancy on S1634593 produces a VARIANCE match record (or both sides unmatched with no match record — per reviewer-disposition spec).

### Stage 10 — Run lifecycle

1. `runs` table.
2. State machine enforcement.
3. Run creation endpoint.
4. Run state transition endpoints.
5. Signing records.
6. Scope selection and transaction `run_id` population.
7. Frontend: run list, run detail, match review UI.

**Acceptance:** Create a run for Feb 2026 on the template profile. Run classification. Run matching. Submit for review. Reviewer accepts. Approver approves. All signing records present. Transactions flipped to RECONCILED.

### Stage 11 — BRS composition and outputs

1. BRS composition function (Section 7.3).
2. BRS.xlsx renderer using openpyxl.
3. Notes.xlsx renderer.
4. PDF renderer using WeasyPrint.
5. Output endpoints.

**Acceptance:** Generated BRS.xlsx reproduces the template's numbers exactly. Notes.xlsx shows all categories correctly. PDF includes signatures.

### Stage 12 — Audit log and reporting

1. Audit log write hooks on all state-changing actions.
2. Audit log query endpoints.
3. Frontend: audit log viewer with filters.

**Acceptance:** Every action in a reconciliation run appears in the audit log with correct actor and diff.

### Stage 13 — Platform admin UI

1. Platform admin login flow.
2. Tenant list / detail / create UI.
3. Tenant suspension and deletion UI.
4. Platform audit log UI.

**Acceptance:** Platform admin can provision a new tenant, invite its admin, and walk the tenant through first-run setup.

### Stage 14 — Polish

1. Email templates for notifications.
2. Error pages (404, 500, session expired).
3. Loading states throughout.
4. Basic dashboard with recent activity.
5. Documentation: README, API docs (FastAPI auto-generates), runbooks.

**Acceptance:** A new tenant can self-serve from invitation email through first approved reconciliation without external help.

### Stage 15 — Hardening

1. Input validation on every endpoint.
2. Rate limiting (basic, per-IP on auth endpoints).
3. CSRF protection where applicable.
4. Security headers.
5. Penetration test readiness.

**Acceptance:** A security review checklist passes.

---

## 18. Out of scope for v1

Explicitly not part of v1. Do not implement. Schema may accommodate them for future expansion; code should not.

- **Billing and subscription management.** `tenants.plan` exists but is unused beyond FREE.
- **Per-tenant branding.** Logos, colors, custom email templates. Deferred.
- **Multi-currency.** `profiles.currency` exists but v1 only supports NGN.
- **Auto-scheduled reconciliation runs.** Only manual initiation.
- **API-based bank statement pulls.** Only file upload.
- **OCR for scanned PDF statements.** Only xlsx/csv.
- **Rate limiting.** Basic IP-based on auth only; full per-user/per-tenant rate limiting deferred.
- **Notification preferences per user.** All relevant users notified; no opt-out.
- **"Trust this device for 30 days" MFA bypass.** Every session requires MFA if enabled.
- **Digital PDF signing with real certificates.** Visual signature blocks only.
- **Export to accounting systems** (QuickBooks, Sage, etc.). Deferred.
- **Mobile apps.** Web-responsive only.
- **i18n.** English only.
- **Prometheus metrics, structured logging, tracing.** Standard FastAPI `logger.info` is sufficient.
- **Upload correction workflow** (replacing a previously-ingested transaction). Manual SQL intervention documented in runbook; automated in v2.
- **Mutation testing.**
- **Chaos testing, load testing.** Basic perf targets documented; no formal load tests.
- **Tenant data export via UI.** Platform-admin-triggered only.

---

## 19. Open questions and assumptions

### 19.1 Assumptions documented

1. **Reconciliation convention.** The "Adjusted GL" approach (GL ± differences = adjusted; compare to BS) is the house style at YCTMFB. If a future tenant uses the "from BS" approach instead (BS ± differences = adjusted; compare to GL), the `brs_template_json` accommodates this but the computation logic needs a new branch. Flag: verify with each new tenant.

2. **Nigerian bank narration patterns.** The classification rules in the appendix are derived from WEMA's Feb 2026 narration style. Other Nigerian banks (Zenith, GTB, Access) have different patterns. New tenants will need to build their own rulesets. The default ruleset ships with WEMA-style patterns only.

3. **Amount tolerance defaults.** ₦1,000 absolute or 0.1% relative as variance tolerance. This is a guess based on the ₦600 discrepancy observed in the template. Real-world tolerance may need tuning after first production runs.

4. **Clearing window.** 15 days default. Observed in the template data: up to 14 days between WEMA credit and YCTMFB GL posting. 15 is conservative.

5. **Bank statement sign convention.** The app assumes every uploaded statement follows standard bank convention: debit = money out, credit = money in from the account holder's perspective as the bank reports. If a tenant uploads a file that inverts this, the column mapping MUST map `debit_source_column` to the app's `credit_amount` field (i.e., the mapping itself can invert).

### 19.2 Unresolved questions

1. **Re-reconciliation after correction.** If a bank re-issues a statement with corrections, and the tenant's already-approved prior run included the uncorrected data, the "supersede" flow handles it — but the UX for walking through which transactions changed is not fully designed. v1: use supersede with tenant-admin intervention; v2: automated diff UI.

2. **What happens to floating items that never match.** If a floating item sits un-matched for 12+ months, is it automatically archived? v1: no automatic archival; they remain visible in every run's unmatched list. v2: configurable auto-archival policy.

3. **Dispute flow.** If the reviewer disagrees with the preparer, the current flow is return-with-note. No structured discussion thread. v2: comments thread on each match record.

4. **Timezone handling.** All timestamps UTC internally. Displayed as Africa/Lagos (UTC+1) in the UI. Is this correct for all future tenants? (Yes for Nigerian microfinance banks; other tenants may need per-tenant timezone.)

5. **Password policy.** Min 12 chars, require mixed case + digit + symbol. Is this strong enough? Aligned with NIST SP 800-63B current guidance. Acceptable for v1.

### 19.3 Questions to answer before v2

1. Do tenants want to export historical runs to an accounting system?
2. Is the matching threshold tunable per profile sufficient, or do tenants want per-category tuning?
3. Should rules support "chained" categorization (rule A matches first, then rule B refines)?

---

## 20. Appendix — reference data from the supplied template

### 20.1 Observed category patterns (default ruleset)

Priority ordering matters; lower priority evaluated first.

| Priority | Name | Side | Dr/Cr | Condition (prose) | Target category |
|---|---|---|---|---|---|
| 10 | Stamp duty | BS | DEBIT | narration starts with "STAMP DUTY" | `electronic_money_transfer` |
| 20 | Account maintenance | BS | DEBIT | narration contains "Account Maintenance Fee" OR "Vat Account Maintenance Fee" | `account_maintenance` |
| 30 | Transfer charges | BS | DEBIT | narration starts with "COMM - " OR "VAT - " | `transfer_charges` |
| 40 | Remita wallet top-up | BS | DEBIT | narration contains "YCT M-TOP-UP" OR "Processing Fees:" | `remita_wallet_topup` |
| 50 | Remita bulk credit (small) | BS | CREDIT | narration matches `^R-\d+/Bulk Credit` AND amount < 20000 | `remita_bulk_credit` |
| 100 | BS debit fallback | BS | DEBIT | always | `bs_debit_generic` |
| 110 | BS credit fallback | BS | CREDIT | always | `bs_credit_generic` |
| 200 | CB debit fallback | CB | DEBIT | always | `cb_debit_generic` |
| 210 | CB credit fallback | CB | CREDIT | always | `cb_credit_generic` |

### 20.2 Default BRS template mapping

```json
{
  "layout_version": 1,
  "header": {
    "entity_name": "YCT MICROFINANCE BANK LIMITED",
    "address_lines": ["Opp. Zenith Bank Building, Yaba College of Technology,", "Yaba, Lagos."],
    "statement_title_template": "BANK RECONCILIATION STATEMENT AS AT {period_end:%d %B %Y}"
  },
  "lines": [
    {"label": "Closing Balance as per General Ledger", "type": "gl_closing", "major": true},
    {"label": "Add: CREDIT ITEMS", "type": "section_header"},
    {"label": "Credit Transactions in Bank Statement", "type": "bucket", "bucket": "credit_bs_not_in_gl", "indent": 1},
    {"label": "Remita Bulk Credit", "type": "bucket", "bucket": "remita_bulk_credit", "indent": 1},
    {"label": "Credit Transactions in Cash Book", "type": "bucket", "bucket": "credit_cb_not_in_bs", "indent": 1},
    {"label": "", "type": "credit_subtotal"},
    {"label": "", "type": "running_total"},
    {"label": "Less: DEBIT ITEMS", "type": "section_header"},
    {"label": "Debit Transactions in Bank Statement", "type": "bucket", "bucket": "debit_bs_not_in_gl", "indent": 1},
    {"label": "Remita Wallet Top-up & Charges", "type": "bucket", "bucket": "remita_wallet_topup", "indent": 1},
    {"label": "Debit Transactions in Cash Book", "type": "bucket", "bucket": "debit_cb_not_in_bs", "indent": 1},
    {"label": "", "type": "debit_subtotal"},
    {"label": "", "type": "running_total"},
    {"label": "Recurrent Bank Charges", "type": "section_header"},
    {"label": "Account Mtce Charge (AMC & VAT)", "type": "bucket", "bucket": "account_maintenance", "indent": 1},
    {"label": "Electronic Money Transfer", "type": "bucket", "bucket": "electronic_money_transfer", "indent": 1},
    {"label": "Transfer Charges", "type": "bucket", "bucket": "transfer_charges", "indent": 1},
    {"label": "", "type": "charges_subtotal"},
    {"label": "General Ledger Adjusted Balance (GL)", "type": "gl_adjusted", "major": true},
    {"label": "Difference (BS) - (GL)", "type": "difference", "major": true},
    {"label": "Closing Balance as per Bank Statement (BS)", "type": "bs_closing", "major": true}
  ],
  "bucket_population_rules": [
    {"bucket": "credit_bs_not_in_gl", "source": "transactions", "where": {"side": "BS", "credit_amount_gt": 0, "status_in": ["UNMATCHED", "VARIANCE_MATCHED"], "category_not_in": ["remita_bulk_credit"]}},
    {"bucket": "remita_bulk_credit", "source": "transactions", "where": {"side": "BS", "credit_amount_gt": 0, "status_in": ["UNMATCHED", "VARIANCE_MATCHED"], "category": "remita_bulk_credit"}},
    {"bucket": "credit_cb_not_in_bs", "source": "transactions", "where": {"side": "CB", "credit_amount_gt": 0, "status": "UNMATCHED"}},
    {"bucket": "debit_bs_not_in_gl", "source": "transactions", "where": {"side": "BS", "debit_amount_gt": 0, "status_in": ["UNMATCHED", "VARIANCE_MATCHED"], "category": "bs_debit_generic"}},
    {"bucket": "debit_cb_not_in_bs", "source": "transactions", "where": {"side": "CB", "debit_amount_gt": 0, "status_in": ["UNMATCHED", "VARIANCE_MATCHED"], "source_category_ne": "previous_month"}},
    {"bucket": "remita_wallet_topup", "source": "transactions", "where": {"category": "remita_wallet_topup"}},
    {"bucket": "account_maintenance", "source": "transactions", "where": {"category": "account_maintenance"}},
    {"bucket": "electronic_money_transfer", "source": "transactions", "where": {"category": "electronic_money_transfer"}},
    {"bucket": "transfer_charges", "source": "transactions", "where": {"category": "transfer_charges"}}
  ]
}
```

### 20.3 Ground-truth numbers (acceptance test)

For the supplied template (WEMA Feb 2026 vs YCTMFB Feb 2026 with default ruleset and default matching config):

```json
{
  "gl_closing_balance": "207078584.61",
  "credit_items": {
    "credit_bs_not_in_gl": "30022077.79",
    "remita_bulk_credit": "16000.00",
    "credit_cb_not_in_bs": "0.00",
    "total": "30038077.79"
  },
  "subtotal_after_credits": "237116662.40",
  "debit_items": {
    "debit_bs_not_in_gl": "200000000.00",
    "remita_wallet_topup": "3000150.00",
    "debit_cb_not_in_bs": "3511028.71",
    "total": "206511178.71"
  },
  "subtotal_after_debits": "30605483.69",
  "recurrent_charges": {
    "account_maintenance": "3225.38",
    "electronic_money_transfer": "250.00",
    "transfer_charges": "215.00",
    "total": "3690.38"
  },
  "gl_adjusted_balance": "30601793.31",
  "bs_closing_balance": "49131551.32",
  "difference": "18529758.01",
  "informational": {
    "previous_month_items": "5239533.67"
  }
}
```

### 20.4 Observed narration patterns (categorization training data)

Complete list of unique narration prefixes/patterns from the template, for testing the classifier:

BS debits:
- `STAMP DUTY ON: {TXN_ID} {DD-MMM-YY}` (5 occurrences, ₦50 each)
- `COMM - FT BO YCT MICROFINANCE BANK IFO YCT MICROFINANCE B` (4 occurrences, ₦50 each)
- `VAT - FT BO YCT MICROFINANCE BANK IFO YCT MICROFINANCE B` (4 occurrences, ₦3.75 each)
- `FT BO YCT MICROFINANCE BANK IFO YCT MICROFINANCEB` (4 occurrences, large amounts)
- `R-{digits}/YCT M-TOP-UP-REGULAR PA` (1 occurrence)
- `R-{digits}/Processing Fees:{digits}` (1 occurrence)
- `Account Maintenance Fee for {MONTH YEAR}` (1 occurrence)
- `Vat Account Maintenance Fee for {MONTH YEAR}` (1 occurrence)

BS credits:
- `NIP:Paystack-PSST{alphanumeric}071310435` (many)
- `R-{digits}/Bulk Credit  - {digits} - {digits}` (many)
- `N-{digits}/Standing Order Standing Order - DD:{digits} - {date} - {initials}` (several)
- `-{digits}/{name}:StandingOrderStandingOrder-DD:{digits}-{date}:{bank}:-:{digits}` (a few)
- `N-{digits}/REMITA PAY-Income Sharing Payment for YCTMFB ({details})` (1)

CB debits (all prefixed with TxnID reference followed by narration fragment):
- `{TXN_ID} WEM {DD/MM}` — typical pattern with source txnid from WEMA embedded
- `{TXN_ID} WEM R-{digits}/BULK CREDITS {DD/MM}`
- `DEP WEM R-{digits}/BULK CREDITS {DD/MM}`
- `DEP WEM {nnnn}: STUDNT PAYMNT GTWAY {DD/MM}`

### 20.5 Sample rule JSON (copy-paste for implementation)

```json
[
  {
    "priority": 10,
    "name": "Stamp Duty (Electronic Money Transfer)",
    "side": "BS",
    "dr_cr": "DEBIT",
    "condition": {
      "op": "LEAF",
      "field": "narration",
      "operator": "starts_with",
      "value": "STAMP DUTY",
      "case_sensitive": false
    },
    "target_category": "electronic_money_transfer",
    "is_enabled": true
  },
  {
    "priority": 20,
    "name": "Account Maintenance Charge",
    "side": "BS",
    "dr_cr": "DEBIT",
    "condition": {
      "op": "LEAF",
      "field": "narration",
      "operator": "contains",
      "value": "Account Maintenance Fee",
      "case_sensitive": false
    },
    "target_category": "account_maintenance",
    "is_enabled": true
  },
  {
    "priority": 30,
    "name": "Transfer Charges (COMM + VAT)",
    "side": "BS",
    "dr_cr": "DEBIT",
    "condition": {
      "op": "OR",
      "children": [
        {"op": "LEAF", "field": "narration", "operator": "starts_with", "value": "COMM - ", "case_sensitive": false},
        {"op": "LEAF", "field": "narration", "operator": "starts_with", "value": "VAT - ", "case_sensitive": false}
      ]
    },
    "target_category": "transfer_charges",
    "is_enabled": true
  },
  {
    "priority": 40,
    "name": "Remita Wallet Top-up",
    "side": "BS",
    "dr_cr": "DEBIT",
    "condition": {
      "op": "OR",
      "children": [
        {"op": "LEAF", "field": "narration", "operator": "contains", "value": "YCT M-TOP-UP", "case_sensitive": false},
        {"op": "LEAF", "field": "narration", "operator": "contains", "value": "Processing Fees:", "case_sensitive": false}
      ]
    },
    "target_category": "remita_wallet_topup",
    "is_enabled": true
  },
  {
    "priority": 50,
    "name": "Remita Bulk Credit (small)",
    "side": "BS",
    "dr_cr": "CREDIT",
    "condition": {
      "op": "AND",
      "children": [
        {"op": "LEAF", "field": "narration", "operator": "matches_regex", "value": "^R-\\d+/Bulk Credit", "case_sensitive": false},
        {"op": "LEAF", "field": "amount", "operator": "lt", "value": 20000}
      ]
    },
    "target_category": "remita_bulk_credit",
    "is_enabled": true
  }
]
```

### 20.6 Sample column mapping (WEMA statement)

```json
{
  "header_row": 4,
  "data_start_row": 5,
  "columns": {
    "date": {"source_column": "A", "format": "MM/DD/YYYY"},
    "txnid": {"source_column": "B"},
    "narration": {"source_column": "C"},
    "debit": {"source_column": "D", "parser": "ngn_text"},
    "credit": {"source_column": "E", "parser": "ngn_text"},
    "balance": {"source_column": "F", "parser": "ngn_text", "optional": true}
  },
  "opening_balance_cell": null,
  "skip_if_row_matches": []
}
```

### 20.7 Sample column mapping (YCTMFB general ledger)

```json
{
  "header_row": 11,
  "data_start_row": 12,
  "columns": {
    "date": {"source_column": "A", "format": "date_iso"},
    "txnid": {"source_column": "B"},
    "narration": {"source_column": "C"},
    "debit": {"source_column": "D", "parser": "numeric"},
    "credit": {"source_column": "E", "parser": "numeric"},
    "balance": {"source_column": "F", "parser": "numeric", "optional": true}
  },
  "opening_balance_cell": "C6",
  "skip_if_row_matches": [
    {"column": "B", "equals": "SUMMARY"},
    {"column": "B", "equals": "Opening Balance"},
    {"column": "B", "equals": "Total Debit"},
    {"column": "B", "equals": "Total Credit"},
    {"column": "B", "equals": "Closing Balance"}
  ]
}
```

---

**End of PRD v1.0**
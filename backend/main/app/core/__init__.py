"""Cross-cutting foundation primitives shared across domains.

Houses the correctness-critical building blocks that multiple domains depend on
and that must have exactly one source of truth:

- ``state``      — state-machine validator, transition tables, status enums,
                   the verification-status derivation owner, and task-dependency config.
- ``vid``        — non-sequential Verification-ID generator (PRD §4.10).
- ``evidence``   — per-item evidence content-hash helper (PRD §4.5).
- ``sla``        — business-day / Nigerian-holiday SLA calculator (PRD §0.2).
- ``idempotency``— idempotency-key store for payments + entity creation (PRD §4.6).
"""
# Import sub-packages that declare ORM models so that importing ``main.app.core``
# (e.g. from Alembic ``env.py``) registers them on ``BaseEntity.metadata``.
from main.app.core import idempotency as idempotency  # noqa: F401

"""Idempotency-key store (PRD §4.6).

Idempotency keys for **payments + entity creation**; optimistic locking guards
*updates*. A replayed gateway webhook (keyed on the gateway event id) cannot
create two PAID transitions or two receipts; a double-tapped create (common on
flaky mobile networks) cannot create two rows.
"""
from main.app.core.idempotency.models import (  # noqa: F401
    IdempotencyKey,
    IdempotencyStatus,
)

"""Dev-only endpoints for deterministic test automation.

ALL endpoints here are gated by _require_non_prod() which raises HTTP 404 in
production. The router itself is only mounted when ENVIRONMENT != prod
(enforced in domain/__init__.py).

POST /dev/reset  — wipe DB tables + clear KV / Redis OTP+OAuth keys; idempotent.
POST /dev/seed   — insert deterministic test fixtures; idempotent (skips existing).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import create_async_engine
from starlette import status

from main.app.config.settings import settings
from main.app.domain.user.auth.session.models import UserPersona, UserType
from main.app.domain.user.models import User
from main.appodus_utils import BaseEntity, Utils
from main.appodus_utils.config.settings import Environment
from main.appodus_utils.db.redis_utils import RedisUtils
from main.appodus_utils.decorators.transactional import transactional, TransactionSessionPolicy
from main.appodus_utils.db.session import get_db_session_from_context
from kink import di

dev_router = APIRouter(prefix="/dev", tags=["dev"])


# ── Production guard ────────────────────────────────────────────────────────

def _require_non_prod():
    if settings.ENVIRONMENT == Environment.PRODUCTION:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


# ── Seed fixtures ────────────────────────────────────────────────────────────

_SEED_USERS: List[Dict[str, Any]] = [
    {
        "id": "00000000-0000-0000-0000-000000000001",
        "first_name": "Test",
        "last_name": "Verified",
        "email": "test.verified@veriprops.test",
        "email_normalized": "test.verified@veriprops.test",
        "email_verified": True,
        "phone_country_code": "NG",
        "phone_dial_code": "+234",
        "phone": "8010000001",
        "phone_e164": "+2348010000001",
        "phone_verified": True,
        "country_of_residence": "NG",
        "timezone": "Africa/Lagos",
        "preferred_currency": "NGN",
        "user_type": UserType.USER.value,
        "personas": [UserPersona.CUSTOMER.value],
        "password_hash": Utils.get_password_hash("TestPass123!"),
    },
    {
        "id": "00000000-0000-0000-0000-000000000002",
        "first_name": "Test",
        "last_name": "Unverified",
        "email": "test.unverified@veriprops.test",
        "email_normalized": "test.unverified@veriprops.test",
        "email_verified": False,
        "phone_country_code": "NG",
        "phone_dial_code": "+234",
        "phone": "8010000002",
        "phone_e164": "+2348010000002",
        "phone_verified": False,
        "country_of_residence": "NG",
        "timezone": "Africa/Lagos",
        "preferred_currency": "NGN",
        "user_type": UserType.USER.value,
        "personas": [UserPersona.CUSTOMER.value],
        "password_hash": Utils.get_password_hash("TestPass123!"),
    },
    {
        "id": "00000000-0000-0000-0000-000000000003",
        "first_name": "Test",
        "last_name": "Admin",
        "email": "test.admin@veriprops.test",
        "email_normalized": "test.admin@veriprops.test",
        "email_verified": True,
        "phone_country_code": "NG",
        "phone_dial_code": "+234",
        "phone": "8010000003",
        "phone_e164": "+2348010000003",
        "phone_verified": True,
        "country_of_residence": "NG",
        "timezone": "Africa/Lagos",
        "preferred_currency": "NGN",
        "user_type": UserType.ADMIN.value,
        "personas": [],
        "password_hash": Utils.get_password_hash("TestPass123!"),
    },
    {
        "id": "00000000-0000-0000-0000-000000000004",
        "first_name": "Test",
        "last_name": "Agent",
        "email": "test.agent@veriprops.test",
        "email_normalized": "test.agent@veriprops.test",
        "email_verified": True,
        "phone_country_code": "NG",
        "phone_dial_code": "+234",
        "phone": "8010000004",
        "phone_e164": "+2348010000004",
        "phone_verified": True,
        "country_of_residence": "NG",
        "timezone": "Africa/Lagos",
        "preferred_currency": "NGN",
        "user_type": UserType.USER.value,
        "personas": [UserPersona.AGENT.value, UserPersona.CUSTOMER.value],
        "password_hash": Utils.get_password_hash("TestPass123!"),
    },
]


# ── DB helpers ───────────────────────────────────────────────────────────────

async def _drop_and_recreate_tables() -> None:
    """Drop all SQLAlchemy-managed tables then recreate them.

    Uses a fresh NullPool engine so we don't interfere with the app's
    connection pool and get a clean slate regardless of pool state.
    """
    engine = create_async_engine(settings.SQLALCHEMY_DATABASE_URI, poolclass=NullPool)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(BaseEntity.metadata.drop_all)
            await conn.run_sync(BaseEntity.metadata.create_all)
    finally:
        await engine.dispose()


async def _flush_kv_keys() -> int:
    """Delete all OTP and OAuth state entries via RedisUtils (Redis or KV fallback)."""
    prefixes = ["otp:", "otp_resend:", "otp_fail:", "otp_verified:", "oauth:"]
    total = 0
    for prefix in prefixes:
        total += await RedisUtils.delete_by_prefix(prefix)
    return total


# ── Seed helper (ALWAYS_NEW so we get our own session independent of the
#    request's DBSessionMiddleware session) ───────────────────────────────────

@transactional(session_policy=TransactionSessionPolicy.ALWAYS_NEW)
async def _upsert_seed_users() -> List[str]:
    session = get_db_session_from_context()
    created: List[str] = []
    for spec in _SEED_USERS:
        uid = uuid.UUID(spec["id"])
        existing = await session.get(User, uid)
        if existing:
            continue
        now = datetime.utcnow()
        user = User(
            id=uid,
            version=1,
            created_at=now,
            updated_at=now,
            deleted=False,
            failed_login_count=0,
            **{k: v for k, v in spec.items() if k != "id"},
        )
        session.add(user)
        created.append(spec["email"])
    return created


# ── Endpoints ────────────────────────────────────────────────────────────────

@dev_router.post("/reset", dependencies=[Depends(_require_non_prod)])
async def dev_reset() -> Dict[str, Any]:
    """Fully reset the database and clear OTP/OAuth KV state.

    Idempotent — safe to call multiple times. Never available in production
    (returns 404).
    """
    await _drop_and_recreate_tables()
    await _flush_kv_keys()
    return {
        "ok": True,
        "message": "Database reset and KV cache cleared.",
    }


@dev_router.post("/seed", dependencies=[Depends(_require_non_prod)])
async def dev_seed() -> Dict[str, Any]:
    """Insert deterministic test fixtures.

    Idempotent — skips users that already exist. Call after /dev/reset for a
    clean slate, or standalone to top-up missing fixtures.

    Seeded users (password for all: TestPass123!):
      test.verified@veriprops.test   — verified CUSTOMER
      test.unverified@veriprops.test — unverified CUSTOMER
      test.admin@veriprops.test      — verified ADMIN
      test.agent@veriprops.test      — verified AGENT+CUSTOMER

    OTP code for all deterministic operations: {otp}
    """.format(otp=settings.TEST_OTP)
    created = await _upsert_seed_users()
    return {
        "ok": True,
        "created": created,
        "skipped": [s["email"] for s in _SEED_USERS if s["email"] not in created],
        "test_otp": str(settings.TEST_OTP),
        "test_password": "TestPass123!",
    }

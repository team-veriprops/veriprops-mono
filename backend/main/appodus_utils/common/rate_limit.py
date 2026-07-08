"""Reusable per-IP rate limiting as a FastAPI dependency.

Sensitive unauthenticated endpoints (login, OTP send/verify, password forgot/reset,
signup) have per-account/per-recipient controls but no edge throttle, leaving
password-reset spam, OTP-send fan-out, and credential-stuffing/lockout-DoS unbounded at
the source IP. `RateLimiter` closes that: a fixed-window counter keyed on
``client_ip + scope`` that raises HTTP 429 past the limit.

Usage (per route)::

    _rl = RateLimiter(scope="otp_send", limit=5, window_seconds=60)

    @router.post("/otp/send")
    async def send_otp(..., _: None = Depends(_rl)):
        ...

The limiter is disabled wholesale when ``settings.DISABLE_RATE_LIMITING`` is true, which
preserves the non-prod automation-determinism contract.
"""
from __future__ import annotations

from starlette.requests import Request

from main.appodus_utils.common.client_utils import ClientUtils
from main.appodus_utils.common.utils_settings import utils_settings
from main.appodus_utils.db.redis_utils import RedisUtils
from main.appodus_utils.exception.exceptions import RateLimitException


class RateLimiter:
    """FastAPI dependency: allow ``limit`` requests per ``window_seconds`` per client IP.

    ``scope`` namespaces the counter so different endpoints throttle independently.
    """

    def __init__(self, *, scope: str, limit: int, window_seconds: int) -> None:
        self._scope = scope
        self._limit = limit
        self._window_seconds = window_seconds

    async def __call__(self, request: Request) -> None:
        if utils_settings.DISABLE_RATE_LIMITING:
            return

        client_ip = ClientUtils.get_client_ip(request) or "unknown"
        key = f"ratelimit:{self._scope}:{client_ip}"
        count = await RedisUtils.incr_with_ttl(key, self._window_seconds)

        if count > self._limit:
            raise RateLimitException(
                service=self._scope,
                message="Too many requests. Please slow down and try again shortly.",
            )

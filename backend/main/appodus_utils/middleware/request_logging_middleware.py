from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger
import secrets
import time
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator, Optional

from kink import di
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger: Logger = di['logger']

# Every response carries the reference in this header, and every error body carries it as
# `error.reference` — the one string that links what a user saw to the log lines behind it.
REQUEST_ID_HEADER = "X-Request-ID"

# The same reference, for code with no `Request` in hand: a fault logged deep inside a service
# carries the reference the user will be shown.
_reference_ctx: ContextVar[Optional[str]] = ContextVar("appodus_request_reference", default=None)


def current_request_reference() -> Optional[str]:
    """The reference of the request being served, or None outside one (a job, a startup task)."""
    return _reference_ctx.get()


@contextmanager
def request_reference_scope(reference: str) -> Iterator[None]:
    """Make *reference* the current request's for the duration of the block."""
    token = _reference_ctx.set(reference)
    try:
        yield
    finally:
        _reference_ctx.reset(token)


def _new_reference() -> str:
    """Eight hex characters: short enough to read off a screenshot, unique enough to find in a log."""
    return secrets.token_hex(4).upper()


def request_reference(request: Request) -> str:
    """The reference for *request*, minting one if the request never passed the logger.

    A failure raised by middleware that runs before this one (edge auth, say) still needs a
    reference to show and to log under, so the error handlers ask here rather than reading
    `request.state` directly.
    """
    reference = getattr(request.state, "reference", None)
    if reference is None:
        reference = _new_reference()
        request.state.reference = reference
    return reference


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        reference = request_reference(request)
        start_time = time.time()

        logger.info(f"[{reference}] Incoming request: {request.method} {request.url.path}")

        try:
            with request_reference_scope(reference):
                response = await call_next(request)
        finally:
            duration = time.time() - start_time
            logger.info(f"[{reference}] Request completed in {duration:.3f}s")

        response.headers[REQUEST_ID_HEADER] = reference
        return response

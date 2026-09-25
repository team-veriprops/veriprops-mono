"""One ERROR per real fault, with its traceback, logged by the first layer that sees it.

Decorators (repo, service, transaction) and the session scope all see an exception on its way
out, and each used to log it at ERROR — so a refused link or a lost race left a screenful of
tracebacks, and a real fault was repeated once per layer. They all call `log_fault_once` now:

- an **expected** outcome is not a fault: a 4xx `AppodusBaseException`, an `ExpectedDomainError`,
  a framework 4xx (a bad token, a malformed body), or a unique violation its caller declared with
  `expecting_violation` (a race it answers). It is logged at DEBUG only;
- a **real** fault is logged at ERROR with its traceback and the request's reference, and marked,
  so every outer layer and the global handler skip it. Logging at the first layer, rather than
  only at the boundary, keeps a fault a best-effort caller swallows from vanishing.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, Iterator, Optional

from fastapi.exceptions import RequestValidationError
from kink import di
from libre_fastapi_jwt.exceptions import AuthJWTException
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

from main.appodus_utils.exception.exceptions import AppodusBaseException, ExpectedDomainError
from main.appodus_utils.middleware.request_logging_middleware import current_request_reference

if TYPE_CHECKING:
    from loguru import Logger

logger: Logger = di["logger"]

_LOGGED_MARK = "_appodus_fault_logged"
_SERVER_ERROR = 500

# Unique indexes whose violation the code running now treats as an answer (see
# `expecting_violation`).
_expected_violations: ContextVar[frozenset[str]] = ContextVar(
    "appodus_expected_violations", default=frozenset()
)


def violated_constraint(error: IntegrityError) -> str:
    """The name of the constraint *error* violated (or the driver's text naming it)."""
    orig = error.orig
    name = getattr(orig, "constraint_name", None)
    if name:
        return str(name)
    # Some drivers wrap asyncpg's exception; its detail still names the constraint.
    return str(orig)


@contextmanager
def expecting_violation(index_name: str) -> Iterator[None]:
    """Within the block, a violation of *index_name* is an expected answer, not a fault."""
    token = _expected_violations.set(_expected_violations.get() | {index_name})
    try:
        yield
    finally:
        _expected_violations.reset(token)


def is_expected_error(exc: BaseException) -> bool:
    """Whether *exc* is an ordinary outcome the caller answers, rather than a fault."""
    if isinstance(exc, AppodusBaseException):
        return exc.status_code < _SERVER_ERROR
    if isinstance(exc, (ExpectedDomainError, AuthJWTException, RequestValidationError)):
        return True
    if isinstance(exc, StarletteHTTPException):
        return exc.status_code < _SERVER_ERROR
    if isinstance(exc, IntegrityError):
        constraint = violated_constraint(exc)
        return any(index in constraint for index in _expected_violations.get())
    return False


def log_fault_once(exc: BaseException, where: str, *, reference: Optional[str] = None) -> bool:
    """Log *exc* at ERROR with its traceback, unless it is expected or already logged.

    *reference* defaults to the current request's. Returns whether this call logged it.
    """
    if is_expected_error(exc):
        logger.debug(f"{where}: {exc!r}")
        return False
    if getattr(exc, _LOGGED_MARK, False):
        return False
    if getattr(exc.__cause__, _LOGGED_MARK, False):
        # A wrapper raised `from` a fault already logged (a safe `HTTPException` for a failure
        # recorded where it happened) is the same fault, not a second one.
        _mark(exc)
        return False
    reference = reference or current_request_reference()
    prefix = f"[{reference}] " if reference else ""
    logger.opt(exception=exc).error(f"{prefix}Fault in {where}: {exc!r}")
    _mark(exc)
    return True


def _mark(exc: BaseException) -> None:
    try:
        setattr(exc, _LOGGED_MARK, True)
    except (AttributeError, TypeError):  # an exception type that takes no attributes
        pass

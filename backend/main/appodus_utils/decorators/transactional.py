from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger
import asyncio
import enum
import functools
from typing import Awaitable, TypeVar, Optional

from main.appodus_utils.db.session import get_db_session_from_context, create_new_db_session
from main.appodus_utils.decorators.audit_ctx import drain_audit_writes, reset_audit_ctx
from kink import di
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import Callable, Concatenate, ParamSpec

from main.appodus_utils.exception.exceptions import AppodusBaseException

logger: Logger = di['logger']
P = ParamSpec("P")
R = TypeVar("R")

class TransactionSessionPolicy(str, enum.Enum):
    """
    Defines how database sessions should be managed during a transaction.
    """
    USE_IF_PRESENT = "use_if_present"
    """
    Use an existing session from the context. Raise an error if no session exists.
    Suitable when the session is guaranteed to be set upstream (e.g., FastAPI dependency).
    """

    ALWAYS_NEW = "always_new"
    """
    Always create a new session and manage the transaction lifecycle independently.
    Use when you want isolation from any existing session context.
    """

    FALLBACK_NEW = "fallback_new"
    """
    Attempt to get the session from the context; if none is found, create a new one.
    Useful when the decorator should be flexible based on usage environment.
    """

def transactional(session_policy: TransactionSessionPolicy = TransactionSessionPolicy.USE_IF_PRESENT):
    """
    Decorator factory that wraps async functions in a DB transaction.

    Args:
        session_policy (TransactionSessionPolicy):
            - USE_IF_PRESENT: Uses existing session from context; raises if none exists.
            - ALWAYS_NEW: Always creates a new session.
            - FALLBACK_NEW: Tries context, creates new session if missing.
    """
    def decorator(func: Callable[Concatenate[P], Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        """
        Decorator that wraps the given async function in a database transaction.

            - Reuses existing transaction if already active.
            - Automatically commits or rolls back the transaction.
            - Logs and re-raises SQLAlchemy errors.
            - Wraps unexpected errors in a AppodusBaseException.
        """
        func_name = getattr(func, "__name__", repr(func))

        @functools.wraps(func)
        async def _wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            try:
                # Support Synchronous Functions Gracefully
                if not asyncio.iscoroutinefunction(func):
                    raise TypeError("@transactional can only be used on async functions")

                db_session: Optional[AsyncSession] = None

                if session_policy == TransactionSessionPolicy.ALWAYS_NEW:
                    async with create_new_db_session() as session:
                        return await execute(func, session, func_name, *args, **kwargs)

                elif session_policy == TransactionSessionPolicy.FALLBACK_NEW:
                    try:
                        db_session = get_db_session_from_context()
                    except LookupError:
                        logger.debug(f"No session in context, creating new session for {func_name}")
                        async with create_new_db_session() as session:
                            return await execute(func, session, func_name, *args, **kwargs)
                    return await execute(func, db_session, func_name, *args, **kwargs)

                elif session_policy == TransactionSessionPolicy.USE_IF_PRESENT:
                    db_session = get_db_session_from_context()
                    return await execute(func, db_session, func_name, *args, **kwargs)

                else:
                    raise AppodusBaseException(f"Unsupported transaction session policy: {session_policy}")

            except Exception as error:
                    error_msg = f"Exception in @transactional(), {func_name}: {error}"
                    logger.error(error_msg)
                    # TimeoutError or
                    raise

        return _wrapper

    return decorator


async def execute(func, db_session: AsyncSession, func_name: str, *args: P.args, **kwargs: P.kwargs):
    logger.debug(f"Checking if {func_name} is in an existing transaction")
    if db_session.in_transaction():
        # Nested: joins an existing transaction owned by the outer @transactional call.
        # Do not drain audit writes here — the outer call will drain after its own flush.
        logger.debug(f"Using existing transaction for {func_name}")
        logger.debug(f"Arguments for {func_name}: args={args}, kwargs={kwargs}")
        call_response = await func(*args, **kwargs)
        await db_session.flush()
        return call_response

    # Outermost: owns begin/commit. Reset the audit queue for a clean slate, then drain
    # after flush so audit rows are committed atomically with the business changes.
    reset_audit_ctx()
    logger.debug(f"Starting transaction for {func_name}")
    async with db_session.begin():
        try:
            logger.debug(f"Arguments for {func_name}: args={args}, kwargs={kwargs}")
            call_response = await func(*args, **kwargs)
            await db_session.flush()
            await drain_audit_writes()
            return call_response
        except SQLAlchemyError as e:
            logger.error(f"SQLAlchemy transaction failed in {func_name}: {e}")
            raise

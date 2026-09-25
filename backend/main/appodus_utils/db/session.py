from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger
import asyncio
import weakref
from contextlib import asynccontextmanager
from contextvars import ContextVar, Token
from typing import AsyncGenerator, Optional, Tuple

from kink import di
from sqlalchemy import NullPool

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession, AsyncEngine

from main.appodus_utils import Utils
from main.appodus_utils.exception.exceptions import AppodusBaseException
from main.appodus_utils.exception.faults import log_fault_once

logger: Logger = di['logger']

IS_SERVERLESS = Utils.get_bool_from_env(env_key="DEPLOYMENT_IS_SERVERLESS", default=False)
DATABASE_URL = Utils.get_from_env_fail_if_not_exists('SQLALCHEMY_DATABASE_URI')
DB_ENABLE_LOGS = Utils.get_bool_from_env(env_key="DB_ENABLE_LOGS", default=True)

engine: Optional[AsyncEngine] = None
AsyncSessionLocal: Optional[async_sessionmaker[AsyncSession]] = None

# Writes that must commit on their own (`TransactionSessionPolicy.INDEPENDENT`) get a separate
# pool. They run while their caller already holds a connection. Drawn from the caller's pool, a
# burst of callers each holding one and waiting for a second exhausts it, and every one of them
# times out together.
independent_engine: Optional[AsyncEngine] = None
IndependentSessionLocal: Optional[async_sessionmaker[AsyncSession]] = None

# Serverless only: the NullPool engine and session factory of each running event loop. A
# platform may run each invocation on a fresh loop, and an engine must not cross loops; one
# engine per session instead would never be disposed. Weak keys drop a loop's entry with it.
_loop_engines: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, Tuple[AsyncEngine, async_sessionmaker[AsyncSession]]]" = (
    weakref.WeakKeyDictionary()
)

# Marks a session opened for an independent write, in `AsyncSession.info`.
_INDEPENDENT_SESSION_MARK = "appodus_independent"

# Pool limits per process when nothing is configured. A burst larger than size + overflow
# queues for the timeout and then fails with a QueuePool TimeoutError.
DEFAULT_POOL_SIZE = 5
DEFAULT_MAX_OVERFLOW = 10
DEFAULT_POOL_TIMEOUT_SECONDS = 30
# Independent writes are short single transactions, so a small pool drains quickly.
DEFAULT_INDEPENDENT_POOL_SIZE = 5
DEFAULT_INDEPENDENT_MAX_OVERFLOW = 5


def create_db_engine_for_env(independent: bool = False) -> AsyncEngine:
    """
    Create an AsyncEngine bound to the *current* event loop.
    - On SERVERLESS: use NullPool to avoid reusing connections across invocations/loops.
    - Elsewhere: a QueuePool sized by DB_POOL_SIZE / DB_MAX_OVERFLOW, or for the independent-write
      engine DB_INDEPENDENT_POOL_SIZE / DB_INDEPENDENT_MAX_OVERFLOW; both wait DB_POOL_TIMEOUT.
    DB_ENABLE_LOG_POOL logs connection checkouts and returns, for diagnosing pool pressure.
    """
    echo_pool = Utils.get_bool_from_env(env_key="DB_ENABLE_LOG_POOL", default=False)

    if IS_SERVERLESS:
        # SERVERLESS/Lambda spins up different loops; pooling can cause cross-loop errors.
        # NullPool opens/closes a connection per session (safe, simpler).
        return create_async_engine(
            DATABASE_URL,
            echo=DB_ENABLE_LOGS,
            echo_pool=echo_pool,
            poolclass=NullPool,
            pool_pre_ping=True,  # still good to verify
            # No pool_recycle with NullPool
        )

    return create_async_engine(
        DATABASE_URL,
        echo=DB_ENABLE_LOGS,
        echo_pool=echo_pool,
        pool_pre_ping=True,
        pool_recycle=1800,  # proactively recycle stale connections (with pool_pre_ping)
        pool_size=(
            Utils.get_int_from_env("DB_INDEPENDENT_POOL_SIZE", default=DEFAULT_INDEPENDENT_POOL_SIZE)
            if independent else Utils.get_int_from_env("DB_POOL_SIZE", default=DEFAULT_POOL_SIZE)
        ),
        max_overflow=(
            Utils.get_int_from_env("DB_INDEPENDENT_MAX_OVERFLOW", default=DEFAULT_INDEPENDENT_MAX_OVERFLOW)
            if independent else Utils.get_int_from_env("DB_MAX_OVERFLOW", default=DEFAULT_MAX_OVERFLOW)
        ),
        pool_timeout=Utils.get_int_from_env("DB_POOL_TIMEOUT", default=DEFAULT_POOL_TIMEOUT_SECONDS),
        pool_reset_on_return="rollback",  # ensures clean state on checkout
    )

def _session_factory(bind: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(bind=bind, expire_on_commit=False, autoflush=False)


def init_db_engine_and_session() -> None:
    global engine, AsyncSessionLocal, independent_engine, IndependentSessionLocal

    if IS_SERVERLESS:
        # Engines are built per event loop on first use (`_serverless_factory`), never here:
        # this loop may not be the one requests run on.
        return

    engine = create_db_engine_for_env()
    AsyncSessionLocal = _session_factory(engine)
    independent_engine = create_db_engine_for_env(independent=True)
    IndependentSessionLocal = _session_factory(independent_engine)


def _serverless_factory() -> async_sessionmaker[AsyncSession]:
    """The running loop's session factory, over its one NullPool engine (built on first use).

    One engine serves both session kinds: NullPool gives every session its own connection,
    so an independent write never waits on its caller's, which is what the separate pool
    exists for elsewhere.
    """
    loop = asyncio.get_running_loop()
    cached = _loop_engines.get(loop)
    if cached is None:
        loop_engine = create_db_engine_for_env()
        cached = (loop_engine, _session_factory(loop_engine))
        _loop_engines[loop] = cached
    return cached[1]


async def close_db_engine():
    logger.info("Disposing DB engines.")
    for pooled in (engine, independent_engine):
        if pooled is not None:
            await pooled.dispose()
    # A serverless engine can only be disposed on its own loop; other loops' entries go with them.
    try:
        cached = _loop_engines.pop(asyncio.get_running_loop(), None)
    except RuntimeError:
        cached = None
    if cached is not None:
        await cached[0].dispose()
    logger.info("...done disposing DB engines.")


db_session_ctx: ContextVar[AsyncSession] = ContextVar("db_session_ctx")

# Add to dependency injector
def get_async_session_for_di(_):
    return get_db_session_from_context()


di[AsyncSession] = get_async_session_for_di


@asynccontextmanager
async def create_new_db_session(independent: bool = False) -> AsyncGenerator[AsyncSession, None]:
    """Open a session and make it the context session until the block exits.

    `independent=True` opens it from the independent-write pool and marks it, so an independent
    write nested inside it joins it instead of taking another connection.
    """
    logger.debug("Creating async database session.")

    if IS_SERVERLESS:
        factory = _serverless_factory()
    else:
        factory = IndependentSessionLocal if independent else AsyncSessionLocal
        if not factory:
            raise AppodusBaseException("DB Session factory not initialized")

    async with factory() as session:
        if independent:
            session.info[_INDEPENDENT_SESSION_MARK] = True
        token = set_db_session_context(session)
        logger.debug("Database session context set.")
        try:
            yield session
            logger.debug("Database session yielded successfully.")
        except Exception as exc:
            # Re-raised as itself: its text (SQL, parameters, a host error) belongs in the log,
            # never in an exception message a handler could render to a client. Logged here only
            # if no inner layer did — a commit that fails as a job's scope closes, say.
            log_fault_once(exc, "database session")
            raise
        finally:
            db_session_ctx.reset(token)
            logger.debug("Database session context reset.")


def set_db_session_context(session: AsyncSession) -> Token[AsyncSession]:
    return db_session_ctx.set(session)


def get_db_session_or_none() -> Optional[AsyncSession]:
    """The context session, or None outside a request/job."""
    return db_session_ctx.get(None)


def is_independent_session(session: Optional[AsyncSession]) -> bool:
    """Whether *session* was opened for an independent write (see `create_new_db_session`)."""
    info = getattr(session, "info", None)
    return isinstance(info, dict) and info.get(_INDEPENDENT_SESSION_MARK) is True


def get_db_session_from_context() -> AsyncSession:
    error_msg = (
        "No database session found in context. "
        "Make sure to call this function within @transactional or a request context using get_db_session."
    )
    try:
        session = db_session_ctx.get()
    except LookupError:
        raise LookupError(error_msg)
    if session is None:
        raise LookupError(error_msg)
    return session

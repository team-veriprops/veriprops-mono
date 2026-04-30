from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger
from contextlib import asynccontextmanager
from contextvars import ContextVar, Token
from typing import AsyncGenerator, Optional

from kink import di
from sqlalchemy import NullPool

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession, AsyncEngine

from main.appodus_utils import Utils
from main.appodus_utils.exception.exceptions import AppodusBaseException

logger: Logger = di['logger']

IS_SERVERLESS = Utils.get_bool_from_env(env_key="DEPLOYMENT_IS_SERVERLESS", default=False)
DATABASE_URL = Utils.get_from_env_fail_if_not_exists('SQLALCHEMY_DATABASE_URI')
DB_ENABLE_LOGS = Utils.get_bool_from_env(env_key="DB_ENABLE_LOGS", default=True)

engine: Optional[AsyncEngine] = None
AsyncSessionLocal: Optional[async_sessionmaker[AsyncSession]] = None

def create_db_engine_for_env() -> AsyncEngine:
    """
    Create an AsyncEngine bound to the *current* event loop.
    - On SERVERLESS: use NullPool to avoid reusing connections across invocations/loops.
    - Elsewhere: use QueuePool with safe settings.
    """
    if IS_SERVERLESS:
        # SERVERLESS/Lambda spins up different loops; pooling can cause cross-loop errors.
        # NullPool opens/closes a connection per session (safe, simpler).
        return create_async_engine(
            DATABASE_URL,
            echo=DB_ENABLE_LOGS,
            poolclass=NullPool,
            pool_pre_ping=True,  # still good to verify
            # No pool_recycle with NullPool
        )
    else:
        # Normal servers: regular pooling is fine
        return create_async_engine(
            DATABASE_URL,
            echo=DB_ENABLE_LOGS,
            pool_pre_ping=True,
            pool_recycle=1800,          # proactively recycle (MySQL default wait_timeout ~8h; adjust to your infra)
            pool_size=5,              # tune
            max_overflow=10,           # tune
            pool_reset_on_return="rollback",  # ensures clean state on checkout
        )
    # engine = create_async_engine(
    #     DATABASE_URL,
    #     echo=DB_ENABLE_LOGS,
    #     query_cache_size=500,
    #     future=True,
    #     pool_pre_ping=True,
    #     pool_recycle=300,
    #     echo_pool=True,
    #     pool_size=5,
    #     max_overflow=10
    # )
    # AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)

def init_db_engine_and_session() -> None:
    global engine, AsyncSessionLocal

    engine = create_db_engine_for_env()

    if IS_SERVERLESS:
        # Do NOT persist in globals in serverless (to avoid cross-loop issues)
        AsyncSessionLocal = None
    else:
        AsyncSessionLocal = async_sessionmaker(
            bind=engine,
            expire_on_commit=False,
            autoflush=False,
        )

async def close_db_engine():
    logger.info("Disposing DB engine.")
    if engine is not None:
        await engine.dispose()
    logger.info("...done disposing DB engine.")


db_session_ctx: ContextVar[AsyncSession] = ContextVar("db_session_ctx")

# Add to dependency injector
def get_async_session_for_di(_):
    return get_db_session_from_context()


di[AsyncSession] = get_async_session_for_di


@asynccontextmanager
async def create_new_db_session() -> AsyncGenerator[AsyncSession, None]:
    global engine, AsyncSessionLocal

    logger.debug("Creating async database session.")

    if IS_SERVERLESS:
        # New engine + session factory each request
        engine = create_db_engine_for_env()
        AsyncSessionLocal = async_sessionmaker(
            bind=engine,
            expire_on_commit=False,
            autoflush=False,
        )
    else:
        if not AsyncSessionLocal:
            raise AppodusBaseException("DB Session factory not initialized")

    async with AsyncSessionLocal() as session:
        token = set_db_session_context(session)
        logger.debug("Database session context set.")
        try:
            yield session
            logger.debug("Database session yielded successfully.")
        except Exception as e:
            error_msg = f"Exception during DB session usage: {e}"
            logger.exception(error_msg)
            raise AppodusBaseException(error_msg)
        finally:
            db_session_ctx.reset(token)
            logger.debug("Database session context reset.")


def set_db_session_context(session: AsyncSession) -> Token[AsyncSession]:
    return db_session_ctx.set(session)


def get_db_session_from_context() -> AsyncSession:
    error_msg = (
        "No database session found in context. "
        "Make sure to call this function within @transactional or a request context using get_db_session."
    )
    try:
        session = db_session_ctx.get()
    except LookupError:
        raise AppodusBaseException(error_msg)
    if session is None:
        raise AppodusBaseException(error_msg)
    return session

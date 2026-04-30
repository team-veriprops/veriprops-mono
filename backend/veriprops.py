from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger

from contextlib import asynccontextmanager

from libre_fastapi_jwt.exceptions import AuthJWTException
from starlette import status

from main.app.config.settings import settings # noqa: F401
from main.appodus_utils.config.bootstrap import BaseDiBootstrap # noqa: F401
from main.app.db.seeder import DataSeeder
from main.appodus_utils.integrations.webhook import webhook_router
from main.appodus_utils.config.client_manager import ClientStateManager

# from main.app.domain.user.auth.active_auditor.global_context import init_auth_context
from main.appodus_utils.exception.exception_handlers import (
    appodus_exception_handler,
    http_error_handler,
    validation_exception_handler,
    generic_exception_handler,
    authjwt_exception_handler
)
from main.appodus_utils.exception.exceptions import AppodusBaseException
from main.appodus_utils.middleware.db_session_middleware import DBSessionMiddleware
from main.appodus_utils.middleware.request_logging_middleware import RequestLoggingMiddleware
from fastapi import FastAPI, Depends
from fastapi.exceptions import RequestValidationError
from kink import di
from starlette.exceptions import HTTPException
from starlette.middleware.cors import CORSMiddleware

from main.app.domain import router

logger: Logger = di['logger']
client_state_manager: ClientStateManager = ClientStateManager()
data_seeder: DataSeeder = DataSeeder()


@asynccontextmanager
async def lifespan_event(app: FastAPI):
    logger.debug("Running lifespan..")

    await client_state_manager.init_clients()
    # Seed data
    await data_seeder.run_data_seed()

    logger.debug("Done running lifespan")
    yield
    logger.debug("Shutting down veriprops...")
    await client_state_manager.close_clients()
    logger.debug("Veriprops is shutdown!")


app = FastAPI(
    redirect_slashes=False,
    lifespan=lifespan_event,
    # dependencies=[Depends(init_auth_context)]
)

# Routers
router.include_router(webhook_router)
app.include_router(router, prefix="/api")

# Exception Handlers
# Custom appodus exceptions
app.add_exception_handler(AppodusBaseException, appodus_exception_handler)
# AuthJWTException
app.add_exception_handler(AuthJWTException, authjwt_exception_handler)
# FastAPI built-in ones
app.add_exception_handler(HTTPException, http_error_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
# Catch-all fallback
app.add_exception_handler(Exception, generic_exception_handler)
#
# # Middlewares
# app.add_middleware(ClientAuthMiddleware)
app.add_middleware(DBSessionMiddleware)
app.add_middleware(RequestLoggingMiddleware)
# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.ALLOWED_ORIGINS.split(',') if origin.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "X-TIMEZONE", "X-LOCALE", "X-CSRF-Token"], )


@app.get("/health", status_code=status.HTTP_200_OK)
def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    # logger.logger.error("Starting dev server:")
    uvicorn.run(app, host="0.0.0.0", port=8000)

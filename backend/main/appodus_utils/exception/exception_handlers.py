import json
import os
import traceback
from logging import Logger

from fastapi import Request
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from libre_fastapi_jwt.exceptions import AuthJWTException
from kink import di
from starlette import status
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response, RedirectResponse
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR

from main.appodus_utils.exception.exceptions import AppodusBaseException

logger: Logger = di["logger"]


async def appodus_exception_handler(request: Request, exc: AppodusBaseException):
    logger.warning(f"{exc.code}: {exc.message}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message
            }
        },
    )


# in production, you can tweak performance using orjson response
def authjwt_exception_handler(request: Request, exc: AuthJWTException):
    logger.warning(f"{exc.status_code}: {exc.message}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.status_code,
                "message": exc.message
            }
        },
    )


async def http_error_handler(request: Request, exc: StarletteHTTPException):
    return await http_exception_handler(request, exc)


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    print(exc)
    return await request_validation_exception_handler(request, exc)


async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {str(exc)}")
    logger.debug(traceback.format_exc())

    ENVIRONMENT: str = os.getenv('ENVIRONMENT', "Environment.PRODUCTION")

    if ENVIRONMENT == "Environment.DEVELOPMENT":
        return JSONResponse(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": str(exc),
                    "trace": traceback.format_exc(),
                }
            },
        )
    else:
        return JSONResponse(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Something went wrong.",
                }
            },
        )

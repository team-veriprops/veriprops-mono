from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger
import os
import traceback

from fastapi import Request
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from libre_fastapi_jwt.exceptions import AuthJWTException
from kink import di
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR

from main.appodus_utils.exception.exceptions import AppodusBaseException

logger: Logger = di["logger"]


def exception_json_response(exc: AppodusBaseException) -> JSONResponse:
    """The API's error envelope for *exc*.

    Shared by the global handler and by endpoints that must *return* an error rather than raise it:
    a raised exception is rendered as a fresh response here, so anything set on the endpoint's own
    response — cookie deletions on a rejected session refresh, say — would never reach the browser.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message
            }
        },
    )


async def appodus_exception_handler(request: Request, exc: AppodusBaseException):
    logger.warning(f"{exc.code}: {exc.message}")
    return exception_json_response(exc)


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

    ENVIRONMENT: str = os.getenv('ENVIRONMENT', "prod")

    if ENVIRONMENT not in ("prod", "staging"):
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

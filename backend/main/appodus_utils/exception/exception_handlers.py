from __future__ import annotations
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from loguru import Logger

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
from main.appodus_utils.exception.faults import log_fault_once
from main.appodus_utils.middleware.request_logging_middleware import (
    REQUEST_ID_HEADER,
    request_reference,
)

logger: Logger = di["logger"]

# What every server-side failure says, in every environment. A 5xx is the one error a user can do
# nothing about, and its own text is the one most likely to carry internals — SQL and its
# parameters, a host error, a provider's reply — so the real text goes to the log under the
# request's reference and never into a response.
SERVER_ERROR_MESSAGE = "Something went wrong on our side. Please try again."
SERVER_ERROR_CODE = "INTERNAL_ERROR"


def _where(request: Request) -> str:
    return f"{request.method} {request.url.path}"


def _is_server_error(status_code: int) -> bool:
    return status_code >= HTTP_500_INTERNAL_SERVER_ERROR


def _envelope(status_code: int, code: str, message: str, reference: Optional[str]) -> JSONResponse:
    error = {"code": code, "message": message}
    headers = None
    if reference:
        error["reference"] = reference
        headers = {REQUEST_ID_HEADER: reference}
    return JSONResponse(status_code=status_code, content={"error": error}, headers=headers)


def exception_json_response(exc: AppodusBaseException, reference: Optional[str] = None) -> JSONResponse:
    """The API's error envelope for *exc*.

    Shared by the global handler and by endpoints that must *return* an error rather than raise it:
    a raised exception is rendered as a fresh response here, so anything set on the endpoint's own
    response — cookie deletions on a rejected session refresh, say — would never reach the browser.

    A 4xx message is copy written for the user and passes through. A 5xx keeps its status and code,
    which callers branch on, but always says `SERVER_ERROR_MESSAGE`.
    """
    message = SERVER_ERROR_MESSAGE if _is_server_error(exc.status_code) else exc.message
    return _envelope(exc.status_code, exc.code, message, reference)


async def appodus_exception_handler(request: Request, exc: AppodusBaseException):
    reference = request_reference(request)
    if _is_server_error(exc.status_code):
        # With its traceback, unless the layer it left already logged it under this reference.
        log_fault_once(exc, _where(request), reference=reference)
    else:
        logger.warning(f"[{reference}] {exc.code}: {exc.message}")
    return exception_json_response(exc, reference)


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
    # A 5xx `HTTPException` is raised with provider or storage text as its detail
    # ("S3 upload failed: …"); it gets the same envelope as every other server failure.
    if _is_server_error(exc.status_code):
        reference = request_reference(request)
        log_fault_once(exc, _where(request), reference=reference)
        return _envelope(exc.status_code, SERVER_ERROR_CODE, SERVER_ERROR_MESSAGE, reference)
    return await http_exception_handler(request, exc)


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning(f"[{request_reference(request)}] Request validation failed: {exc.errors()}")
    return await request_validation_exception_handler(request, exc)


async def generic_exception_handler(request: Request, exc: Exception):
    reference = request_reference(request)
    # The detail survives only in the log: at error level, with its traceback, under the
    # reference the user is shown — once, if the layer it left has not already logged it.
    log_fault_once(exc, _where(request), reference=reference)
    return _envelope(HTTP_500_INTERNAL_SERVER_ERROR, SERVER_ERROR_CODE, SERVER_ERROR_MESSAGE, reference)

import time
from logging import Logger
from uuid import uuid4

from kink import di
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger: Logger = di['logger']

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid4())
        start_time = time.time()

        logger.info(f"[{request_id}] Incoming request: {request.method} {request.url.path}")

        try:
            response = await call_next(request)

        finally:
            duration = time.time() - start_time
            logger.info(f"[{request_id}] Request completed in {duration:.3f}s")

        return response

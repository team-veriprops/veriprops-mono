from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from main.appodus_utils.db.session import create_new_db_session


class DBSessionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        async with create_new_db_session():
            response = await call_next(request)

        return response

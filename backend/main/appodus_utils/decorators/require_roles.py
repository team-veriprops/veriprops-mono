import functools
from logging import Logger
from typing import Callable

from fastapi import HTTPException
from kink import di

logger: Logger = di['logger']

def require_roles(*roles: str) -> Callable:
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            request: Request = kwargs.get("request")
            token = await oauth2_scheme(request)
            user_data = fake_users_db.get(token)
            if not user_data:
                raise HTTPException(status_code=401, detail="Invalid credentials")
            if user_data["role"] not in roles:
                raise HTTPException(status_code=403, detail="Insufficient permissions")
            request.state.user = User(**user_data)
            return await func(*args, **kwargs)
        return wrapper
    return decorator
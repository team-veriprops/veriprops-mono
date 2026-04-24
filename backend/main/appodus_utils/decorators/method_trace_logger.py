import functools
import inspect
import traceback
from typing import Callable, Awaitable, Any
from logging import Logger
from kink import di

AsyncCallable = Callable[..., Awaitable[Any]]
logger: Logger = di['logger']


def _unwrap_func(maybe_func: Callable) -> Callable:
    """Unwrap staticmethod or classmethod to get the underlying function."""
    if isinstance(maybe_func, (staticmethod, classmethod)):
        return maybe_func.__func__
    return maybe_func


def method_trace_logger(func: AsyncCallable) -> AsyncCallable:
    real_func = _unwrap_func(func)  # Ensure we check the actual function

    @functools.wraps(real_func)  # Preserve metadata
    async def _wrapper(*args, **kwargs) -> Awaitable[Any]:
        try:
            logger.debug(f"Calling function {real_func}, with params {args} and {kwargs}")

            if inspect.iscoroutinefunction(real_func):
                return_value = await real_func(*args, **kwargs)
            else:
                return_value = real_func(*args, **kwargs)

            logger.debug(f"Return value is {return_value}")
            return return_value
        except Exception as e:
            logger.exception(
                f"An error occurred: {''.join(traceback.format_exception(None, e, e.__traceback__))}"
            )
            raise

    return _wrapper

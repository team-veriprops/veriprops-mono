import inspect
from typing import Callable


def decorate_all_methods(
    decorator: Callable,
    exclude: list[str] = None,
    exclude_startswith: list[str] = None
):
    excluded = ['__init__', '__module__', '_session', '__dict__', '__weakref__', '__doc__']
    startswith_excluded = ["_", "__"]

    if exclude:
        excluded.extend(exclude)
    if exclude_startswith:
        startswith_excluded.extend(exclude_startswith)

    def decorate(cls):
        # Names of the methods this decorator wrapped that were **not** coroutine
        # functions to begin with. Recorded because the wrapper hides the fact: after
        # decoration every method looks async, so the only moment the original shape is
        # visible is right here. A synchronous method wrapped by an async decorator does
        # not run when called — it returns a coroutine the caller drops — and that has
        # shipped twice as a silent no-op. `test_decorated_service_contract.py` reads this.
        wrapped_sync: list[str] = []
        for attr_name, attr_value in list(cls.__dict__.items()):
            if (
                callable(attr_value)
                and attr_name not in excluded
                and not attr_name.startswith(tuple(startswith_excluded))
            ):
                original = (
                    attr_value.__func__
                    if isinstance(attr_value, (staticmethod, classmethod))
                    else attr_value
                )
                if inspect.isfunction(original) and not inspect.iscoroutinefunction(original):
                    wrapped_sync.append(attr_name)
                setattr(cls, attr_name, decorator(attr_value))
        cls._appodus_wrapped_sync_methods = tuple(
            sorted(set(getattr(cls, "_appodus_wrapped_sync_methods", ())) | set(wrapped_sync))
        )
        return cls

    return decorate


# def decorate_all_methods(decorator: callable, exclude=None, exclude_startswith: str = None):
#     if exclude is None:
#         exclude = []
#
#     def decorate(cls):
#         for attr in cls.__dict__:
#             if (callable(getattr(cls, attr)) and (attr not in exclude) and
#                     (not exclude_startswith or not attr.startswith(exclude_startswith))):
#                 setattr(cls, attr, decorator(getattr(cls, attr)))
#         return cls
#
#     return decorate

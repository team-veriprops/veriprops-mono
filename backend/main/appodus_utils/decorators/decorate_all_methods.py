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
        for attr_name, attr_value in cls.__dict__.items():
            if (
                callable(attr_value)
                and attr_name not in excluded
                and not attr_name.startswith(tuple(startswith_excluded))
            ):
                setattr(cls, attr_name, decorator(attr_value))
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

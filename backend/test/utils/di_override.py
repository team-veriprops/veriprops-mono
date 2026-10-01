"""Swap a DI service for a test double, whether or not an earlier test already resolved it.

kink memoizes an `@inject`-registered service the first time it is resolved and answers from
that cache before `_services`, so overriding `_services` alone is silently ignored once any
earlier test has resolved the real object — the test then passes or fails depending on the
order the suite runs in.
"""
from typing import Any

from kink import di


def override_service(monkeypatch, key: Any, value: Any) -> None:
    """Resolve *key* to *value* for this test; both maps are restored afterwards."""
    monkeypatch.setitem(di._services, key, value)
    monkeypatch.setitem(di._memoized_services, key, value)

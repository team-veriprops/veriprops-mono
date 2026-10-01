"""The mounted route table: every (method, path) is served by exactly one handler.

FastAPI accepts the same router being included twice and silently keeps both copies; the
first one wins, and the second is dead weight that looks live. Routers are mounted once,
in `main/app/domain/__init__.py`, and this guard keeps it that way.
"""
from collections import Counter

from fastapi.routing import APIRoute

from veriprops import app


def _route_keys() -> Counter:
    keys: Counter = Counter()
    for route in app.routes:
        if isinstance(route, APIRoute):
            for method in route.methods:
                keys[(method, route.path)] += 1
    return keys


def test_no_route_is_mounted_twice():
    duplicates = {key: count for key, count in _route_keys().items() if count > 1}
    assert not duplicates, f"routes mounted more than once: {sorted(duplicates)}"


def test_the_provider_webhooks_are_still_mounted():
    keys = _route_keys()
    for key in [
        ("GET", "/api/webhooks/{platform}/redirect"),
        ("GET", "/api/webhooks/{platform}"),
        ("POST", "/api/webhooks/{platform}"),
    ]:
        assert keys[key] == 1, key

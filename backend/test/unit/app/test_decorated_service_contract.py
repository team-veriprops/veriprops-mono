"""No public method on a `decorate_all_methods` class may be synchronous.

This guard exists because the same defect shipped twice in one slice, and both times it
was **invisible at the call site**:

* a `@staticmethod` DTO mapper on a decorated service returned a coroutine, and the
  endpoint answered 500 while every log line read as success;
* a synchronous `seed_draft_payload` returned a coroutine its caller dropped on the floor,
  so a customer's chat answers silently never reached their draft — found only by a live
  drive-through.

`decorate_all_methods(transactional())` wraps *every* public method — plain `def` and
`staticmethod` alike — into a coroutine function. A synchronous method therefore does not
run when called: it returns an un-awaited coroutine, and Python's only complaint is a
warning nobody reads in a test run. Nothing else catches it. Mocks stand in for the
service in unit tests, mypy sees the wrapper's `(*args, **kwargs)` signature, and ruff has
no opinion.

So the rule is structural. If a method genuinely must be synchronous — a pure mapper, a
formatter — move it to **module level**, where the class decorator cannot reach it. That
is what `to_bot_session_dto` does.

The census is taken by the decorator itself, at decoration time, because that is the only
moment the original shape is still visible.
"""
from __future__ import annotations

import inspect
import sys

import pytest

# `main.app.domain` is the app's single aggregation point — importing it pulls in every
# domain exactly as the running app does. The census reads `sys.modules` afterwards rather
# than walking the package tree: a class the app never imports is never decorated at
# runtime either, so the app's own import graph is exactly the right scope. (Walking the
# tree also drags in dead modules, one of which registers an orphan ORM table and makes
# the migration-parity guard fail — a test must not change what another test sees.)
import main.app.domain  # noqa: F401

_MARKER = "_appodus_wrapped_sync_methods"
_PACKAGES = ("main.app.", "main.appodus_utils.")


def _decorated_classes():
    """Every class `decorate_all_methods` touched in the loaded app.

    Discovered rather than listed: a hand-kept list would go stale on exactly the day
    someone adds the service that reintroduces the bug.
    """
    seen = {}
    for name, module in list(sys.modules.items()):
        if not name.startswith(_PACKAGES) or module is None:
            continue
        for obj in vars(module).values():
            if not inspect.isclass(obj) or obj.__module__ != name:
                continue
            if hasattr(obj, _MARKER):
                seen[f"{obj.__module__}.{obj.__name__}"] = obj
    return [seen[key] for key in sorted(seen)]


_DECORATED = _decorated_classes()


def test_the_census_actually_found_the_decorated_services():
    """A guard that silently stops seeing anything is worse than no guard: it reports
    success forever. This is the canary for an import or marker change."""
    assert len(_DECORATED) > 20, f"only found {len(_DECORATED)} decorated classes"


@pytest.mark.parametrize("cls", _DECORATED, ids=lambda c: f"{c.__module__}.{c.__name__}")
def test_no_public_method_is_synchronous(cls):
    offenders = list(getattr(cls, _MARKER, ()))

    assert not offenders, (
        f"{cls.__module__}.{cls.__name__} has synchronous public method(s) {offenders}. "
        f"`decorate_all_methods` wraps them into coroutine functions, so calling one "
        f"returns a coroutine nobody awaits and the method silently does nothing. Make it "
        f"`async def`, or move it to module level if it is genuinely pure."
    )

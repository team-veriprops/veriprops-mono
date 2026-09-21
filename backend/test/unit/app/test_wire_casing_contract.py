"""Wire-casing contract guard.

Every request/response DTO inherits `Object`, whose alias generator makes the wire
camelCase while Python stays snake_case (root CLAUDE.md, "API casing"). FastAPI's
`Body(..., embed=True)` sidesteps that entirely: it binds the **raw Python parameter
name**, so a multi-word parameter silently demands snake_case from clients that send
camelCase everywhere else.

That is not a theoretical risk — `POST /payments/stub/confirm` shipped expecting
`tx_ref` while the frontend sent `txRef`, and the mismatch is invisible until something
calls it and gets a 422. This test fails the moment another one appears.
"""
from __future__ import annotations

import ast
from pathlib import Path

# backend/test/unit/app/<this file> -> backend/
_BACKEND_ROOT = Path(__file__).resolve().parents[3]
_APP_ROOT = _BACKEND_ROOT / "main" / "app"


def _embedded_body_params(tree: ast.AST) -> list[str]:
    """Parameter names bound with `Body(..., embed=True)` in any route handler."""
    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        args = node.args
        for arg, default in zip(
            args.args[len(args.args) - len(args.defaults):], args.defaults
        ):
            if not isinstance(default, ast.Call):
                continue
            func = default.func
            name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
            if name != "Body":
                continue
            embedded = any(
                kw.arg == "embed" and isinstance(kw.value, ast.Constant) and kw.value.value
                for kw in default.keywords
            )
            if embedded:
                found.append(arg.arg)
    return found


def test_no_snake_case_body_parameter_escapes_the_camelcase_contract():
    offenders: dict[str, list[str]] = {}
    for path in _APP_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        multiword = [name for name in _embedded_body_params(tree) if "_" in name]
        if multiword:
            offenders[str(path.relative_to(_BACKEND_ROOT))] = multiword

    assert not offenders, (
        "These `Body(..., embed=True)` parameters bind a snake_case name straight from "
        "the wire, bypassing the camelCase alias generator every other DTO uses. Declare "
        f"an `Object` DTO for the request body instead: {offenders}"
    )

"""Every write that can break the commission margin goes through the guard (§20.1 / D97).

A tier's margin depends on six stored values: the roles' fixed commissions, the tier prices, the
minimum margin, the remote bonus and the two discount percentages. `CommissionMarginGuard` refuses a change that would breach
it, but only when the writer calls it — so a new writer that forgets is exactly the defect that
lets the two admin screens drift into paying agents more than the platform keeps. This scan finds
every write to the three repositories holding those values, in `main/app`, with no database, and
pins them: the known writers, each calling the guard before it writes.

A new writer fails here. Route it through `CommissionMarginGuard.check` and add it to
`_GUARDED_WRITERS`; don't weaken the scan.
"""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Dict, Iterator, List, Set, Tuple

_APP_ROOT = Path(__file__).resolve().parents[5] / "main" / "app"

# The repositories whose rows feed the margin, and the GenericRepo methods that write a row.
_GUARDED_REPOS = {"CommissionRuleRepo", "PricingTierConfigRepo", "SystemConfigRepo"}
_WRITE_METHODS = {"upsert", "create", "create_return_model", "update", "insert_or_get", "soft_delete"}

# (class, method) → the writer's reason to exist. Each must call the guard before writing.
_GUARDED_WRITERS: Dict[Tuple[str, str], str] = {
    ("CommissionRuleService", "set_rule"): "a role's fixed commission",
    ("PricingConfigService", "set_tier_pricing"): "a tier's price (with its line items)",
    ("ConfigService", "set"): "the minimum margin, the remote bonus and the discounts (among other keys)",
}
# The config keys whose writes must reach the guard inside ConfigService.set.
_MARGIN_CONFIG_KEYS = {
    "COMMISSION_MIN_MARGIN_PCT", "REMOTE_JOB_BONUS_NGN_KOBO",
    "FIRST_TIME_DISCOUNT_PERCENT", "MAX_DISCOUNT_PERCENT",
}


def _classes() -> Iterator[Tuple[Path, ast.ClassDef]]:
    for path in sorted(_APP_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                yield path, node


def _repo_attributes(cls: ast.ClassDef) -> Set[str]:
    """The `self.<attr>` names an __init__ binds to one of the guarded repositories."""
    init = next((n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "__init__"), None)
    if init is None:
        return set()
    typed_params = {
        a.arg for a in init.args.args
        if isinstance(a.annotation, ast.Name) and a.annotation.id in _GUARDED_REPOS
    }
    attrs = set()
    for stmt in ast.walk(init):
        if (isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Name)
                and stmt.value.id in typed_params):
            for target in stmt.targets:
                if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) \
                        and target.value.id == "self":
                    attrs.add(target.attr)
    return attrs


def _is_self_attr_call(call: ast.Call, attrs: Set[str], methods: Set[str]) -> bool:
    func = call.func
    return (isinstance(func, ast.Attribute) and func.attr in methods
            and isinstance(func.value, ast.Attribute) and func.value.attr in attrs
            and isinstance(func.value.value, ast.Name) and func.value.value.id == "self")


def _methods(cls: ast.ClassDef):
    return [n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]


def _writes() -> Dict[Tuple[str, str], List[int]]:
    """(class, method) → the line of every write it makes to a guarded repository."""
    found: Dict[Tuple[str, str], List[int]] = {}
    for _path, cls in _classes():
        attrs = _repo_attributes(cls)
        if not attrs:
            continue
        for method in _methods(cls):
            for node in ast.walk(method):
                if isinstance(node, ast.Call) and _is_self_attr_call(node, attrs, _WRITE_METHODS):
                    found.setdefault((cls.name, method.name), []).append(node.lineno)
    return found


def _method(class_name: str, method_name: str) -> ast.AST:
    for _path, cls in _classes():
        if cls.name == class_name:
            for method in _methods(cls):
                if method.name == method_name:
                    return method
    raise AssertionError(f"{class_name}.{method_name} not found")


def _guard_calls(node: ast.AST) -> List[int]:
    return [
        n.lineno for n in ast.walk(node)
        if isinstance(n, ast.Call) and _is_self_attr_call(n, {"_margin_guard"}, {"check"})
    ]


_WRITES = _writes()


def test_the_scan_finds_the_known_writers():
    # Guards against this test passing vacuously if the scan ever stops finding writes.
    assert set(_GUARDED_WRITERS) <= set(_WRITES)


def test_no_unguarded_writer_exists():
    unknown = set(_WRITES) - set(_GUARDED_WRITERS)
    assert not unknown, (
        f"{sorted(unknown)} write a price, a commission or a config value without being a known "
        "margin-guarded writer — call CommissionMarginGuard.check before the write and add it "
        "to _GUARDED_WRITERS"
    )


def test_each_writer_checks_the_margin_before_it_writes():
    for (class_name, method_name), what in _GUARDED_WRITERS.items():
        guard_lines = _guard_calls(_method(class_name, method_name))
        assert guard_lines, f"{class_name}.{method_name} writes {what} without the margin guard"
        assert min(guard_lines) < min(_WRITES[(class_name, method_name)]), (
            f"{class_name}.{method_name} writes before it checks the margin"
        )


def test_config_writes_of_every_margin_key_reach_the_guard():
    """ConfigService.set writes every key; the guard must run for the four the margin reads."""
    guarded_keys: Set[str] = set()
    for node in ast.walk(_method("ConfigService", "set")):
        if isinstance(node, ast.If) and any(_guard_calls(stmt) for stmt in node.body):
            guarded_keys |= {
                n.attr for n in ast.walk(node.test)
                if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)
                and n.value.id == "ConfigKey"
            }
    assert _MARGIN_CONFIG_KEYS <= guarded_keys, (
        f"ConfigService.set stores {sorted(_MARGIN_CONFIG_KEYS - guarded_keys)} without the margin guard"
    )

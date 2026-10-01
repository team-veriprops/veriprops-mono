"""The migration chain builds every live-only unique guard the models declare, and the SLA marker.

Lookups skip soft-deleted rows, so a unique guard on a soft-deletable table is a partial index
(`WHERE deleted = false`), declared on the model with `live_unique_index(...)` and built by the
migration under the same name — `insert_or_get` targets it by columns and predicate, so the two
must agree exactly. Pinned in both directions, with no database: each `_create_<table>()` builder
runs against a recording stand-in for alembic's `op`, and then every additive revision after `0001`
replays its `upgrade()` against the same stand-in, so a guard a later revision drops or creates
(`0002_fixed_agent_commission` re-keys `commission_rules` by role), or takes with a dropped table
(`0008_drop_signup_drafts`), is folded into what "built" means.

`0001`'s revision id is the last revision folded into it, so a database already stamped there is
left alone by the squash (backend/CLAUDE.md, "Squashing the chain back into 0001").
"""
import importlib.util
import re
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import sqlalchemy as sa

from main.app import core as _core, domain as _domain
from main.appodus_utils import BaseEntity

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
_VERSIONS = _BACKEND_ROOT / "main" / "alembic" / "versions"
_MIGRATION = _VERSIONS / "0001_initial_schema.py"
_HEAD = "0019_sla_breach_marker"


def _norm(sql: str) -> str:
    return re.sub(r"\s+", " ", str(sql).replace("(", " ( ").replace(")", " ) ")).strip().lower()


def _load(path: Path = _MIGRATION):
    spec = importlib.util.spec_from_file_location(f"live_uniqueness_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _later_revisions():
    """Every revision after `0001`, in chain order (each names its predecessor in `down_revision`)."""
    modules = [_load(path) for path in sorted(_VERSIONS.glob("*.py")) if path != _MIGRATION]
    by_parent = {m.down_revision: m for m in modules}
    ordered, parent = [], _HEAD
    while parent in by_parent:
        ordered.append(by_parent[parent])
        parent = ordered[-1].revision
    assert len(ordered) == len(modules), "a revision is not reachable from 0001's head"
    return ordered


def _record_builders():
    """Run every table builder against a recording `op`; return its create_table/create_index calls."""
    module = _load()
    recorder = MagicMock()
    module.op = recorder
    for _name, builder in module._TABLE_BUILDERS:
        builder()
    tables = {call.args[0]: call.args[1:] for call in recorder.create_table.call_args_list}
    indexes = [call for call in recorder.create_index.call_args_list if isinstance(call.args[0], str)]
    constraints = [call for call in recorder.create_unique_constraint.call_args_list]
    return module, tables, indexes, constraints


def _replay_later_revisions():
    """Run each later revision's `upgrade()` against a recording `op`; return the index names and
    table names it dropped and the create_index calls it made, in order."""
    dropped, dropped_tables, created = [], [], []
    for revision in _later_revisions():
        recorder = MagicMock()
        revision.op = recorder
        revision.upgrade()
        dropped += [call.args[0] for call in recorder.drop_index.call_args_list]
        dropped_tables += [call.args[0] for call in recorder.drop_table.call_args_list]
        created += [call for call in recorder.create_index.call_args_list if isinstance(call.args[0], str)]
    return dropped, dropped_tables, created


_MODULE, _TABLES, _INDEXES, _UNIQUE_CONSTRAINTS = _record_builders()
_DROPPED_LATER, _TABLES_DROPPED_LATER, _CREATED_LATER = _replay_later_revisions()


def _partial_unique(call) -> bool:
    return call.kwargs.get("unique") is True and "postgresql_where" in call.kwargs


def _model_partial_uniques():
    _ = (_core, _domain)
    return {
        index.name: (table.name, [c.name for c in index.columns], index.dialect_options["postgresql"]["where"])
        for table in BaseEntity.metadata.tables.values()
        for index in table.indexes
        if index.unique and index.dialect_options["postgresql"]["where"] is not None
    }


_MODEL_GUARDS = _model_partial_uniques()
_BUILT_GUARDS = {
    call.args[0]: (call.args[1], list(call.args[2]), call.kwargs["postgresql_where"])
    for call in _INDEXES
    if _partial_unique(call) and call.args[0] not in _DROPPED_LATER and call.args[1] not in _TABLES_DROPPED_LATER
}
_BUILT_GUARDS.update({
    call.args[0]: (call.args[1], list(call.args[2]), call.kwargs["postgresql_where"])
    for call in _CREATED_LATER
    if _partial_unique(call)
})


def test_it_is_the_one_root_and_carries_the_last_folded_revision():
    assert (_MODULE.revision, _MODULE.down_revision) == (_HEAD, None)


def test_the_models_declare_live_only_guards():
    # Guards against this test passing vacuously if the model scan ever stops finding them.
    assert len(_MODEL_GUARDS) >= 18


@pytest.mark.parametrize("name", sorted(_MODEL_GUARDS))
def test_every_guard_a_model_declares_is_built_the_same(name):
    table, columns, where = _MODEL_GUARDS[name]
    assert name in _BUILT_GUARDS, f"the migration chain never builds {name}"
    built_table, built_columns, built_where = _BUILT_GUARDS[name]
    assert (built_table, built_columns) == (table, columns)
    assert _norm(built_where) == _norm(where)


@pytest.mark.parametrize("name", sorted(_BUILT_GUARDS))
def test_every_guard_the_chain_builds_is_declared_on_a_model(name):
    assert name in _MODEL_GUARDS, f"the migration chain builds {name}, which no model declares"


@pytest.mark.parametrize("name", sorted(_MODEL_GUARDS))
def test_no_full_table_constraint_shadows_a_live_only_guard(name):
    # A leftover full-table UniqueConstraint of the same name would still block re-creating a
    # soft-deleted row — the defect the live-only guards exist to remove.
    table, _columns, _where = _MODEL_GUARDS[name]
    # A table a later revision created has no 0001 constraints to leave behind.
    constraint_names = {item.name for item in _TABLES.get(table, ()) if isinstance(item, sa.UniqueConstraint)}
    assert name not in constraint_names
    assert name not in {call.args[0] for call in _UNIQUE_CONSTRAINTS}


def test_the_sla_breach_marker_is_built_nullable_after_the_audit_columns():
    # Where `ADD COLUMN` put it on a migrated database, so a fresh build matches column-for-column.
    columns = [item for item in _TABLES["verifications"] if isinstance(item, sa.Column)]
    names = [column.name for column in columns]
    marker = columns[names.index("sla_breach_notified_at")]
    assert marker.nullable
    assert names[-1] == "sla_breach_notified_at"

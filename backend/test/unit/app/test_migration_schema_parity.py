"""Schema/migration parity guard.

The project runs in a single-migration (`0001_initial_schema`) greenfield
posture: every table is built by a `_create_<table>()` helper registered in
`_TABLE_BUILDERS`. A model added without a matching builder produces a mapped
entity whose table `alembic upgrade head` never creates — every query against
it then 500s at runtime. This guard fails CI the moment that drift appears,
in both directions — including framework/vendored entities (e.g. `devices`,
`callbacks`) that live outside `domain/**`.
"""
import importlib.util
from pathlib import Path

# Importing these packages registers every model onto BaseEntity.metadata,
# exactly mirroring what alembic/env.py does to build the autogenerate target.
from main.app import core as _core, domain as _domain
from main.appodus_utils import BaseEntity

# backend/test/unit/app/<this file> -> backend/ is parents[3].
_BACKEND_ROOT = Path(__file__).resolve().parents[3]


def _load_initial_migration():
    migration_path = _BACKEND_ROOT / "main" / "alembic" / "versions" / "0001_initial_schema.py"
    spec = importlib.util.spec_from_file_location("veriprops_initial_migration", migration_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _builder_tables() -> set[str]:
    return {table_name for table_name, _builder in _load_initial_migration()._TABLE_BUILDERS}


def _mapped_tables() -> set[str]:
    _ = (_core, _domain)  # keep the model-registering imports live
    return set(BaseEntity.metadata.tables.keys())


def test_every_entity_table_has_a_migration_builder():
    orphaned = _mapped_tables() - _builder_tables()
    assert not orphaned, (
        f"BaseEntity tables with no migration builder (will 500 at runtime): {sorted(orphaned)}"
    )


def test_no_migration_builder_without_a_mapped_entity():
    dead_ddl = _builder_tables() - _mapped_tables()
    assert not dead_ddl, (
        f"Migration builders with no mapped entity (dead DDL): {sorted(dead_ddl)}"
    )


def test_no_same_name_duplicate_indexes_in_any_model():
    """A column declared with inline `index=True` whose auto-name (`ix_<table>_<col>`)
    collides with an explicit `__table_args__` `Index(same_name, ...)` yields two index
    objects with the same name on one table — a latent bug that breaks create_all /
    autogenerate. Declare each index once."""
    _ = (_core, _domain)
    offenders = {}
    for table_name, table in BaseEntity.metadata.tables.items():
        names = [index.name for index in table.indexes]
        dupes = sorted({name for name in names if names.count(name) > 1})
        if dupes:
            offenders[table_name] = dupes
    assert not offenders, f"Tables with same-name duplicate indexes: {offenders}"

"""Migration 0005 reconciles the database's indexes and keys with the models.

The full proof is `alembic check` against a migrated database, which the backend CI
`migrations` job runs and which must report nothing. These tests pin the model side of the
decisions it rests on, so a later edit cannot quietly reintroduce the drift:

* the primary key is the only index on `id`, and the soft-delete flag is not indexed;
* uniqueness lives in unique indexes, not constraint + plain index pairs;
* the migration chains after 0004 and is the only head.
"""
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from main.app import domain as _domain  # noqa: F401 — registers every model
from main.appodus_utils import BaseEntity

_BACKEND_ROOT = Path(__file__).resolve().parents[3]


def _scripts() -> ScriptDirectory:
    config = Config()
    config.set_main_option("script_location", str(_BACKEND_ROOT / "main" / "alembic"))
    return ScriptDirectory.from_config(config)


def test_it_chains_after_the_payout_migration_and_is_the_only_head():
    scripts = _scripts()
    assert scripts.get_heads() == ["0005_schema_parity"]
    assert scripts.get_revision("0005_schema_parity").down_revision == "0004_payout_transfers"


def _indexed_columns(table):
    return {tuple(c.name for c in index.columns) for index in table.indexes}


def test_no_table_indexes_its_primary_key_or_the_soft_delete_flag_again():
    for table in BaseEntity.metadata.tables.values():
        columns = _indexed_columns(table)
        assert ("id",) not in columns, table.name
        assert ("deleted",) not in columns, table.name


def test_the_swapped_keys_are_unique_indexes():
    tables = BaseEntity.metadata.tables
    for table, index in [
        ("payments", "ix_payments_tx_ref"),
        ("verifications", "ix_verifications_vid"),
        ("users", "ix_users_email_normalized"),
        ("verification_shares", "ix_verification_shares_token"),
        ("referrals", "ix_referrals_code"),
    ]:
        by_name = {i.name: i for i in tables[table].indexes}
        assert by_name[index].unique is True, index

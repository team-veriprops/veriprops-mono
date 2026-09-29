"""Migration 0006 keeps the reviewer's KYC photos by reference, additively.

It must chain after 0005, leave the history with a single head, and add exactly the nullable
columns the KYC record declares.
"""
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from main.app.domain.user.agent.kyc.models import KycRecord

_BACKEND_ROOT = Path(__file__).resolve().parents[3]


def _scripts() -> ScriptDirectory:
    config = Config()
    config.set_main_option("script_location", str(_BACKEND_ROOT / "main" / "alembic"))
    return ScriptDirectory.from_config(config)


def test_it_chains_after_the_schema_parity_migration_and_is_the_only_head():
    scripts = _scripts()
    assert scripts.get_heads() == ["0006_kyc_images"]
    assert scripts.get_revision("0006_kyc_images").down_revision == "0005_schema_parity"


def test_the_model_declares_what_the_migration_creates():
    columns = KycRecord.__table__.c
    assert (columns.id_type.type.length, columns.selfie_key.type.length, columns.document_key.type.length) == (24, 255, 255)
    assert all(columns[name].nullable for name in ("id_type", "selfie_key", "document_key"))

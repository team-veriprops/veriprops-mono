import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect
from alembic import op

from main.appodus_utils.db.models import UTCDateTime

class AlembicUtils:

    @staticmethod
    def base_audit_columns():
        """Mirror BaseEntity audit columns."""
        return [
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("date_created", UTCDateTime, nullable=False),
            sa.Column("created_by", sa.String(length=36), nullable=True),
            sa.Column("date_updated", UTCDateTime, nullable=True),
            sa.Column("updated_by", sa.String(length=36), nullable=True),
            sa.Column("deleted", sa.Boolean(), nullable=False),
            sa.Column("date_deleted", UTCDateTime, nullable=True),
            sa.Column("deleted_by", sa.String(length=36), nullable=True),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        ]

    @staticmethod
    def table_exists(name: str) -> bool:
        bind = op.get_bind()
        return name in sa_inspect(bind).get_table_names()

    @staticmethod
    def refuse_if_rows(count_sql: str, what: str) -> None:
        """Abort the upgrade instead of destroying data a step would otherwise lose.

        *count_sql* counts the rows the next step would delete, overwrite or strip of a value.
        A non-zero count raises, and because `env.py` runs every pending revision inside one
        transaction, Postgres rolls the whole upgrade back: the database stays at the revision
        it started on and the deploy stops before new code ships. Put it immediately before the
        lossy statement it protects. On a fresh or already-clean database it is a no-op.
        """
        rows = op.get_bind().execute(sa.text(count_sql)).scalar() or 0
        if rows:
            raise RuntimeError(
                f"Refusing to migrate: {rows} row(s) would lose data ({what}). "
                "Nothing has been changed. Preserve or reconcile these rows first, then re-run."
            )


import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect
from alembic import op

from main.appodus_utils.db.models import UTCDateTime

class AlembicUtils:

    @staticmethod
    def base_audit_columns():
        """Mirror BaseEntity audit columns."""
        return [
            sa.Column("id", sa.String(length=36), nullable=False),
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

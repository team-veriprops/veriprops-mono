"""kyc_images — the photos a reviewer compares, kept by reference on the KYC record.

A live identity check sends the applicant's selfie to Dojah. When the application then reaches
a reviewer, the selfie — and for a passport, driver's licence or voter's card, a photo of the
document — is kept in private, encrypted storage, so the reviewer can compare them side by
side. The record holds only the storage keys (read through short-lived links) and the ID type
the comparison is labelled by. Erasure deletes the objects and clears the keys.

Additive and nullable: a record from before this, or one whose check failed, has no photos.

Revision ID: 0006_kyc_images
Revises: 0005_schema_parity
Create Date: 2026-09-28 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006_kyc_images"
down_revision: Union[str, None] = "0005_schema_parity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "kyc_records"


def upgrade() -> None:
    op.add_column(_TABLE, sa.Column("id_type", sa.String(length=24), nullable=True))
    op.add_column(_TABLE, sa.Column("selfie_key", sa.String(length=255), nullable=True))
    op.add_column(_TABLE, sa.Column("document_key", sa.String(length=255), nullable=True))


def downgrade() -> None:
    # Drops the keys only; the stored objects are removed by erasure, not by a schema change.
    op.drop_column(_TABLE, "document_key")
    op.drop_column(_TABLE, "selfie_key")
    op.drop_column(_TABLE, "id_type")

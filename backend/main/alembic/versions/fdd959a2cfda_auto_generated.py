"""auto_generated

Revision ID: fdd959a2cfda
Revises: 
Create Date: 2025-06-01 02:19:26.646342

"""
from datetime import datetime
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import JSON
from sqlalchemy.ext.mutable import MutableList

# revision identifiers, used by Alembic.
revision: str = 'fdd959a2cfda'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def create_tab_key_values():
    op.create_table('key_values', sa.Column('key', sa.String(length=128), nullable=False),
                    sa.Column('value', sa.LargeBinary(), nullable=False),
                    sa.Column('expires_at', sa.DateTime(), nullable=False),
                    sa.PrimaryKeyConstraint('key'))
    op.create_index(op.f('ix_key_values_key'), 'key_values', ['key'], unique=True)


def drop_tab_key_values():
    op.drop_index(op.f('ix_key_values_key'), table_name='key_values')
    op.drop_table('key_values')


def create_tab_banks():
    op.create_table('banks',
                    sa.Column('name', sa.String(length=40), nullable=False),
                    sa.Column('short_name', sa.String(length=10), nullable=False),
                    sa.Column('code', sa.String(length=6), nullable=False),
                    sa.Column('status', sa.String(length=12), nullable=False),
                    sa.Column('country_code', sa.String(length=20), nullable=False),

                    sa.Column('id', sa.String(length=36), nullable=False),
                    sa.Column('date_created', sa.TIMESTAMP(timezone=True), nullable=False),
                    sa.Column('created_by', sa.String(length=36), nullable=True),
                    sa.Column('date_updated', sa.TIMESTAMP(timezone=True), nullable=True),
                    sa.Column('updated_by', sa.String(length=36), nullable=True),
                    sa.Column('deleted', sa.Boolean(), nullable=False),
                    sa.Column('date_deleted', sa.TIMESTAMP(timezone=True), nullable=True),
                    sa.Column('deleted_by', sa.String(length=36), nullable=True),
                    sa.Column('version', sa.Integer(), nullable=False),
                    sa.PrimaryKeyConstraint('id'))
    op.create_index(op.f('ix_banks_deleted'), 'banks', ['deleted'], unique=False)
    op.create_index(op.f('ix_banks_id'), 'banks', ['id'], unique=True)


def drop_tab_banks():
    op.drop_index(op.f('ix_banks_id'), table_name='banks')
    op.drop_index(op.f('ix_banks_deleted'), table_name='banks')
    op.drop_table('banks')



def upgrade() -> None:
    create_tab_key_values()
    create_tab_banks()


def downgrade() -> None:
    drop_tab_key_values()
    drop_tab_banks()

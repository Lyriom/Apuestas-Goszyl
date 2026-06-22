"""featured_content.post_id int -> varchar (acepta UUID de Sistema A)

Revision ID: 202606220001
Revises: 202605040001
Create Date: 2026-06-22 00:01:00
"""
from alembic import op
import sqlalchemy as sa

revision = '202606220001'
down_revision = '202605040001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        'featured_content',
        'post_id',
        existing_type=sa.Integer(),
        type_=sa.String(length=64),
        existing_nullable=False,
        postgresql_using='post_id::varchar',
    )


def downgrade() -> None:
    op.alter_column(
        'featured_content',
        'post_id',
        existing_type=sa.String(length=64),
        type_=sa.Integer(),
        existing_nullable=False,
        postgresql_using='post_id::integer',
    )

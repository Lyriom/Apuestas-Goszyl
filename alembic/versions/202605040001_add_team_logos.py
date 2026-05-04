"""add team logo columns to matches

Revision ID: 202605040001
Revises: 202605030001
Create Date: 2026-05-04 00:01:00
"""
from alembic import op
import sqlalchemy as sa

revision = '202605040001'
down_revision = '202605030001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('matches', sa.Column('home_logo_url', sa.String(length=500), nullable=True))
    op.add_column('matches', sa.Column('away_logo_url', sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column('matches', 'away_logo_url')
    op.drop_column('matches', 'home_logo_url')

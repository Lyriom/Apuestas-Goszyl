"""initial schema

Revision ID: 202605030001
Revises:
Create Date: 2026-05-03 00:01:00
"""
from alembic import op
import sqlalchemy as sa

revision = '202605030001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('users', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('keycloak_id', sa.String(length=128), nullable=False), sa.Column('email', sa.String(length=255), nullable=False), sa.Column('name', sa.String(length=255), nullable=False), sa.Column('roles', sa.JSON(), nullable=False), sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index(op.f('ix_users_keycloak_id'), 'users', ['keycloak_id'], unique=True)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_table('matches', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('tournament', sa.String(length=80), nullable=False), sa.Column('home_team', sa.String(length=160), nullable=False), sa.Column('away_team', sa.String(length=160), nullable=False), sa.Column('kickoff_at', sa.DateTime(timezone=True), nullable=False), sa.Column('status', sa.String(length=32), nullable=False), sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.UniqueConstraint('tournament', 'home_team', 'away_team', 'kickoff_at', name='uq_match_identity'))
    op.create_index(op.f('ix_matches_tournament'), 'matches', ['tournament'])
    op.create_index(op.f('ix_matches_home_team'), 'matches', ['home_team'])
    op.create_index(op.f('ix_matches_away_team'), 'matches', ['away_team'])
    op.create_index(op.f('ix_matches_kickoff_at'), 'matches', ['kickoff_at'])
    op.create_index(op.f('ix_matches_status'), 'matches', ['status'])
    op.create_table('odds', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('match_id', sa.Integer(), sa.ForeignKey('matches.id', ondelete='CASCADE'), nullable=False), sa.Column('bookmaker', sa.String(length=40), nullable=False), sa.Column('home_odd', sa.Numeric(8, 2), nullable=True), sa.Column('draw_odd', sa.Numeric(8, 2), nullable=True), sa.Column('away_odd', sa.Numeric(8, 2), nullable=True), sa.Column('captured_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index(op.f('ix_odds_match_id'), 'odds', ['match_id'])
    op.create_index(op.f('ix_odds_bookmaker'), 'odds', ['bookmaker'])
    op.create_index(op.f('ix_odds_captured_at'), 'odds', ['captured_at'])
    op.create_table('scrape_logs', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('bookmaker', sa.String(length=40), nullable=False), sa.Column('started_at', sa.DateTime(timezone=True), nullable=False), sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True), sa.Column('status', sa.String(length=24), nullable=False), sa.Column('error_msg', sa.Text(), nullable=True), sa.Column('items_count', sa.Integer(), nullable=False))
    op.create_index(op.f('ix_scrape_logs_bookmaker'), 'scrape_logs', ['bookmaker'])
    op.create_index(op.f('ix_scrape_logs_started_at'), 'scrape_logs', ['started_at'])
    op.create_index(op.f('ix_scrape_logs_status'), 'scrape_logs', ['status'])
    op.create_table('featured_content', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('post_id', sa.Integer(), nullable=False), sa.Column('title', sa.String(length=240), nullable=False), sa.Column('excerpt', sa.Text(), nullable=False), sa.Column('content_html', sa.Text(), nullable=False), sa.Column('slug', sa.String(length=260), nullable=False), sa.Column('received_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index(op.f('ix_featured_content_post_id'), 'featured_content', ['post_id'], unique=True)
    op.create_index(op.f('ix_featured_content_slug'), 'featured_content', ['slug'])


def downgrade() -> None:
    op.drop_table('featured_content')
    op.drop_table('scrape_logs')
    op.drop_table('odds')
    op.drop_table('matches')
    op.drop_table('users')

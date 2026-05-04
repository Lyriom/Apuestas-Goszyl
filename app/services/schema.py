from loguru import logger
from sqlalchemy import text

from app import models  # noqa: F401
from app.database import Base, engine

SCHEMA_LOCK_ID = 202605030001

# Idempotent column additions for live PG instances. Listed here because
# `Base.metadata.create_all` only creates missing TABLES, not missing
# COLUMNS — so once a table exists, adding a column to a SQLAlchemy model
# alone does not propagate to prod. Each entry: (table, column, ddl).
LIVE_COLUMNS = (
    ('matches', 'home_logo_url', "ALTER TABLE matches ADD COLUMN IF NOT EXISTS home_logo_url VARCHAR(500)"),
    ('matches', 'away_logo_url', "ALTER TABLE matches ADD COLUMN IF NOT EXISTS away_logo_url VARCHAR(500)"),
)


async def ensure_schema() -> None:
    """Best-effort schema reconciliation at app start.

    Alembic owns `alembic_version` — we never write to it here, since
    racing with `alembic upgrade head` (or with another gunicorn worker)
    can leave multiple rows and break the next deploy with an
    "overlaps" error. Migrations are the source of truth; this only
    backfills tables/columns when running outside the alembic flow.
    """
    async with engine.begin() as connection:
        await connection.execute(text('SELECT pg_advisory_xact_lock(:lock_id)'), {'lock_id': SCHEMA_LOCK_ID})
        await connection.run_sync(Base.metadata.create_all)
        for _table, _col, ddl in LIVE_COLUMNS:
            await connection.execute(text(ddl))
        version = (await connection.execute(text('SELECT version_num FROM alembic_version'))).scalar()
    logger.info('database_schema_ready revision={}', version)

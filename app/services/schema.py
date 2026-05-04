from loguru import logger
from sqlalchemy import text

from app import models  # noqa: F401
from app.database import Base, engine

ALEMBIC_HEAD = '202605040001'
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
    async with engine.begin() as connection:
        await connection.execute(text('SELECT pg_advisory_xact_lock(:lock_id)'), {'lock_id': SCHEMA_LOCK_ID})
        await connection.run_sync(Base.metadata.create_all)
        for _table, _col, ddl in LIVE_COLUMNS:
            await connection.execute(text(ddl))
        await connection.execute(
            text(
                "CREATE TABLE IF NOT EXISTS alembic_version ("
                "version_num VARCHAR(32) NOT NULL, "
                "CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)"
                ")"
            )
        )
        await connection.execute(text("DELETE FROM alembic_version"))
        await connection.execute(
            text("INSERT INTO alembic_version (version_num) VALUES (:version)"),
            {'version': ALEMBIC_HEAD},
        )
    logger.info('database_schema_ready revision={}', ALEMBIC_HEAD)

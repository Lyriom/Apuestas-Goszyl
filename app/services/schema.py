from loguru import logger
from sqlalchemy import text

from app import models  # noqa: F401
from app.database import Base, engine

ALEMBIC_HEAD = '202605030001'
SCHEMA_LOCK_ID = 202605030001


async def ensure_schema() -> None:
    async with engine.begin() as connection:
        await connection.execute(text('SELECT pg_advisory_xact_lock(:lock_id)'), {'lock_id': SCHEMA_LOCK_ID})
        await connection.run_sync(Base.metadata.create_all)
        await connection.execute(
            text(
                "CREATE TABLE IF NOT EXISTS alembic_version ("
                "version_num VARCHAR(32) NOT NULL, "
                "CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)"
                ")"
            )
        )
        await connection.execute(
            text(
                "INSERT INTO alembic_version (version_num) VALUES (:version) "
                "ON CONFLICT (version_num) DO NOTHING"
            ),
            {'version': ALEMBIC_HEAD},
        )
    logger.info('database_schema_ready revision={}', ALEMBIC_HEAD)

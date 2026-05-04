from logging.config import fileConfig

from alembic import context
from alembic.script import ScriptDirectory
from sqlalchemy import pool, text
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.config import get_settings
from app.database import Base
from app import models  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
config.set_main_option('sqlalchemy.url', settings.database_url)
target_metadata = Base.metadata


def _heal_alembic_version(connection) -> None:
    """Fix `alembic_version` rows left in an inconsistent state.

    A previous deploy could insert both an ancestor and its descendant
    into `alembic_version` (e.g. `ensure_schema` writing the head while
    a prior `alembic upgrade head` had already written the new head).
    Alembic then refuses to upgrade with "Requested revision X overlaps
    with other requested revisions Y", and the container crash-loops.

    If we detect more than one row, we collapse to the deepest one
    according to the local script directory's ancestry — that's the
    real DB state because every prior revision's DDL has already run.
    """
    rows = connection.execute(text('SELECT version_num FROM alembic_version')).fetchall()
    if len(rows) <= 1:
        return
    versions = [r[0] for r in rows]
    script = ScriptDirectory.from_config(config)
    known = [v for v in versions if script.get_revision(v) is not None]
    if not known:
        return
    deepest = known[0]
    for candidate in known[1:]:
        if deepest in {r.revision for r in script.iterate_revisions(candidate, 'base')}:
            deepest = candidate
    connection.execute(text('DELETE FROM alembic_version'))
    connection.execute(text('INSERT INTO alembic_version (version_num) VALUES (:v)'), {'v': deepest})


def run_migrations_offline() -> None:
    context.configure(url=settings.database_url, target_metadata=target_metadata, literal_binds=True, dialect_opts={'paramstyle': 'named'})
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    _heal_alembic_version(connection)
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(config.get_section(config.config_ini_section, {}), prefix='sqlalchemy.', poolclass=pool.NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    import asyncio
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

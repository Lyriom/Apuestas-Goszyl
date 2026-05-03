from datetime import UTC, datetime

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ScrapeLog


async def start_log(db: AsyncSession, bookmaker: str) -> ScrapeLog:
    log = ScrapeLog(bookmaker=bookmaker, started_at=datetime.now(UTC), status='running')
    db.add(log)
    await db.flush()
    return log


async def finish_log(db: AsyncSession, log: ScrapeLog, *, status: str, items_count: int = 0, error_msg: str | None = None) -> ScrapeLog:
    log.finished_at = datetime.now(UTC)
    log.status = status
    log.items_count = items_count
    log.error_msg = error_msg
    await db.flush()
    return log


async def latest_logs(db: AsyncSession) -> dict[str, ScrapeLog]:
    logs = list((await db.scalars(select(ScrapeLog).order_by(desc(ScrapeLog.started_at)).limit(80))).all())
    result: dict[str, ScrapeLog] = {}
    for log in logs:
        result.setdefault(log.bookmaker, log)
    return result


async def all_logs(db: AsyncSession, limit: int = 100) -> list[ScrapeLog]:
    return list((await db.scalars(select(ScrapeLog).order_by(desc(ScrapeLog.started_at)).limit(limit))).all())

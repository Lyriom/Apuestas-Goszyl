from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.services.match_service import find_or_create_match, is_target_tournament
from app.services.odd_service import create_odd
from app.services.scrape_log_service import finish_log, start_log


@dataclass(slots=True)
class ScrapedOdd:
    bookmaker: str
    home_team: str
    away_team: str
    kickoff_at: datetime
    home_odd: float | None
    draw_odd: float | None
    away_odd: float | None
    tournament: str = 'LigaPro Ecuador'


class BaseScraper(ABC):
    bookmaker: str
    url: str
    tournament: str = 'LigaPro Ecuador'

    def __init__(self) -> None:
        self.settings = get_settings()

    @abstractmethod
    async def scrape(self) -> list[ScrapedOdd]:
        raise NotImplementedError

    async def run(self) -> int:
        async with AsyncSessionLocal() as db:
            log = await start_log(db, self.bookmaker)
            await db.commit()
            try:
                items = await self.scrape()
                items = [it for it in items if is_target_tournament(it.tournament)]
                saved = await self.save_to_db(db, items)
                await finish_log(db, log, status='ok', items_count=saved)
                await db.commit()
                logger.info('scraper_finished bookmaker={} items={}', self.bookmaker, saved)
                return saved
            except Exception as exc:
                await db.rollback()
                async with AsyncSessionLocal() as error_db:
                    error_log = await error_db.get(type(log), log.id)
                    if error_log:
                        await finish_log(error_db, error_log, status='error', error_msg=str(exc)[:4000])
                        await error_db.commit()
                logger.exception('scraper_failed bookmaker={}', self.bookmaker)
                return 0

    async def save_to_db(self, db: AsyncSession, items: list[ScrapedOdd]) -> int:
        saved = 0
        for item in items:
            match = await find_or_create_match(
                db,
                tournament=item.tournament,
                home_team=item.home_team,
                away_team=item.away_team,
                kickoff_at=item.kickoff_at.astimezone(UTC),
            )
            has_prices = any(v is not None for v in (item.home_odd, item.draw_odd, item.away_odd))
            if has_prices:
                await create_odd(
                    db,
                    match_id=match.id,
                    bookmaker=item.bookmaker,
                    home_odd=item.home_odd,
                    draw_odd=item.draw_odd,
                    away_odd=item.away_odd,
                )
            saved += 1
        return saved

from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

from app.config import get_settings
from app.scrapers.bet593 import Bet593Scraper
from app.scrapers.betano import BetanoScraper
from app.scrapers.betcris import BetcrisScraper
from app.scrapers.ecuabet import EcuabetScraper
from app.scrapers.sofascore import SofascoreScraper

SCRAPER_CLASSES = {
    'sofascore': SofascoreScraper,
    'ecuabet': EcuabetScraper,
    'betcris': BetcrisScraper,
    'bet593': Bet593Scraper,
    'betano': BetanoScraper,
}


async def run_scraper(name: str) -> int:
    scraper_cls = SCRAPER_CLASSES[name]
    logger.info('scraper_starting name={}', name)
    return await scraper_cls().run()


def create_scheduler() -> AsyncIOScheduler:
    settings = get_settings()
    scheduler = AsyncIOScheduler(timezone='UTC')
    now = datetime.utcnow()
    for index, name in enumerate(SCRAPER_CLASSES):
        scheduler.add_job(
            run_scraper,
            'interval',
            args=[name],
            hours=settings.scrapers_interval_hours,
            next_run_time=now + timedelta(seconds=settings.scrapers_initial_run_delay_seconds, minutes=45 * index),
            id=f'scraper-{name}',
            max_instances=1,
            coalesce=True,
            misfire_grace_time=900,
        )
    return scheduler

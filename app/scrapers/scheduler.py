from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

from app.config import get_settings
from app.scrapers.altenar import Bet593Scraper, DoradobetScraper, EcuabetScraper
from app.scrapers.betano import BetanoScraper
from app.scrapers.espn import EspnScraper

# Order matters: ESPN runs first to seed match rows with team logos so the
# bookmaker scrapers later attach odds via find_or_create_match dedup.
# Pinnacle was removed: their guest API returns 403 from the EasyPanel
# datacenter IP (verified in prod logs 2026-05-04). If we re-enable it,
# we'll need a different egress path or a residential proxy.
SCRAPER_CLASSES = {
    'espn': EspnScraper,
    'ecuabet': EcuabetScraper,
    'doradobet': DoradobetScraper,
    'bet593': Bet593Scraper,
    'betano': BetanoScraper,
}

# Casas reales mostradas en el panel admin para monitoreo.
BOOKMAKER_SCRAPERS = ('ecuabet', 'doradobet', 'bet593', 'betano')


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
            next_run_time=now + timedelta(seconds=settings.scrapers_initial_run_delay_seconds, minutes=5 * index),
            id=f'scraper-{name}',
            max_instances=1,
            coalesce=True,
            misfire_grace_time=900,
        )
    return scheduler

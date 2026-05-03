from sqlalchemy import select

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models import Match
from app.scrapers.scheduler import SCRAPER_CLASSES


async def seed_mock_if_empty() -> None:
    settings = get_settings()
    if not settings.scrapers_use_mock:
        return
    async with AsyncSessionLocal() as db:
        exists = await db.scalar(select(Match.id).limit(1))
        if exists:
            return
    for scraper_cls in SCRAPER_CLASSES.values():
        await scraper_cls().run()

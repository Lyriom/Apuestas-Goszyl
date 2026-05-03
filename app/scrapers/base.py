from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from loguru import logger
from playwright.async_api import Browser, async_playwright
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.services.match_service import find_or_create_match
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

    def __init__(self) -> None:
        self.settings = get_settings()

    async def setup_browser(self) -> Browser:
        playwright = await async_playwright().start()
        return await playwright.chromium.launch(headless=True)

    @abstractmethod
    async def scrape(self) -> list[ScrapedOdd]:
        raise NotImplementedError

    async def run(self) -> int:
        async with AsyncSessionLocal() as db:
            log = await start_log(db, self.bookmaker)
            await db.commit()
            try:
                items = await self.scrape()
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

    async def mock_data(self, odds: list[tuple[float, float, float]]) -> list[ScrapedOdd]:
        now = datetime.now(UTC)
        fixtures = [
            ('LigaPro Ecuador', 'Liga de Quito', 'Emelec', 2),
            ('LigaPro Ecuador', 'Barcelona SC', 'Independiente del Valle', 5),
            ('Selección Ecuador', 'Ecuador', 'Colombia', 9),
        ]
        return [
            ScrapedOdd(
                bookmaker=self.bookmaker,
                tournament=tournament,
                home_team=home,
                away_team=away,
                kickoff_at=now.replace(hour=19, minute=0, second=0, microsecond=0) + timedelta(days=days),
                home_odd=o[0],
                draw_odd=o[1],
                away_odd=o[2],
            )
            for (tournament, home, away, days), o in zip(fixtures, odds, strict=True)
        ]

    async def extract_with_playwright(self, selectors: list[str]) -> list[ScrapedOdd]:
        browser = await self.setup_browser()
        try:
            context = await browser.new_context(user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/121 Safari/537.36', locale='es-EC', viewport={'width': 1280, 'height': 720})
            page = await context.new_page()
            await page.goto(self.url, wait_until='domcontentloaded', timeout=45000)
            for selector in selectors:
                try:
                    await page.wait_for_selector(selector, timeout=8000)
                    break
                except Exception:
                    continue
            logger.warning('real_scraper_needs_site_specific_mapping bookmaker={}', self.bookmaker)
            return []
        finally:
            await browser.close()

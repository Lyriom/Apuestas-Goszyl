from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from loguru import logger
from playwright.async_api import Browser, BrowserContext, Page, async_playwright
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.scrapers.parser import parse_events_from_dom
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


USER_AGENT = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
)

COOKIE_BUTTONS = [
    'button:has-text("Aceptar")',
    'button:has-text("Acepto")',
    'button:has-text("Accept")',
    'button:has-text("OK")',
    'button:has-text("Entendido")',
    '[id*="cookie" i] button',
    '[class*="cookie" i] button',
]


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

    async def _setup(self) -> tuple[Browser, BrowserContext, Page]:
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled', '--no-sandbox'],
        )
        context = await browser.new_context(
            user_agent=USER_AGENT,
            locale='es-EC',
            timezone_id='America/Guayaquil',
            viewport={'width': 1366, 'height': 900},
        )
        page = await context.new_page()
        return browser, context, page

    async def _dismiss_overlays(self, page: Page) -> None:
        for selector in COOKIE_BUTTONS:
            try:
                button = page.locator(selector).first
                if await button.count() and await button.is_visible():
                    await button.click(timeout=1500)
                    break
            except Exception:
                continue

    async def _scroll_full_page(self, page: Page, steps: int = 6) -> None:
        for _ in range(steps):
            await page.mouse.wheel(0, 1500)
            await page.wait_for_timeout(700)

    async def fetch_events(self, urls: list[str]) -> list[ScrapedOdd]:
        timeout_ms = self.settings.scrapers_timeout_seconds * 1000
        browser, context, page = await self._setup()
        try:
            collected: list[dict] = []
            for url in urls:
                try:
                    await page.goto(url, wait_until='domcontentloaded', timeout=timeout_ms)
                except Exception as exc:
                    logger.warning('scraper_navigation_failed bookmaker={} url={} err={}', self.bookmaker, url, exc)
                    continue
                await self._dismiss_overlays(page)
                await page.wait_for_timeout(2500)
                await self._scroll_full_page(page)
                try:
                    raw = await page.evaluate(_EVENT_EXTRACTION_JS)
                    if isinstance(raw, list):
                        collected.extend(raw)
                except Exception as exc:
                    logger.warning('scraper_extract_failed bookmaker={} url={} err={}', self.bookmaker, url, exc)
            parsed = parse_events_from_dom(collected, default_kickoff=_default_kickoff())
            results: list[ScrapedOdd] = []
            seen: set[tuple[str, str]] = set()
            for event in parsed:
                key = (event['home'].lower(), event['away'].lower())
                if key in seen:
                    continue
                seen.add(key)
                results.append(ScrapedOdd(
                    bookmaker=self.bookmaker,
                    tournament=self.tournament,
                    home_team=event['home'],
                    away_team=event['away'],
                    kickoff_at=event['kickoff_at'],
                    home_odd=event['home_odd'],
                    draw_odd=event['draw_odd'],
                    away_odd=event['away_odd'],
                ))
            logger.info('scraper_extracted bookmaker={} events={}', self.bookmaker, len(results))
            return results
        finally:
            await context.close()
            await browser.close()


def _default_kickoff() -> datetime:
    return (datetime.now(UTC) + timedelta(days=2)).replace(hour=0, minute=0, second=0, microsecond=0)


_EVENT_EXTRACTION_JS = r"""
() => {
  const oddRe = /^\d{1,2}[.,]\d{2}$/;
  const events = [];
  const seen = new Set();
  const all = document.querySelectorAll('div, section, article, li, tr');
  for (const el of all) {
    const rawText = (el.innerText || '').trim();
    if (!rawText || rawText.length > 600) continue;
    const odds = (rawText.match(/\b\d{1,2}[.,]\d{2}\b/g) || [])
      .map(v => parseFloat(v.replace(',', '.')))
      .filter(v => v >= 1.01 && v <= 99);
    if (odds.length < 3) continue;
    const childTexts = Array.from(el.querySelectorAll('*'))
      .map(c => (c.innerText || c.textContent || '').trim())
      .filter(t => t && t.length < 80);
    const candidates = childTexts.filter(t => /[a-zA-ZÁÉÍÓÚÑáéíóúñ]/.test(t) && !oddRe.test(t.replace(/\s/g, '')));
    const fp = `${rawText.length}:${odds.slice(0, 3).join(',')}:${candidates.slice(0, 4).join('|')}`;
    if (seen.has(fp)) continue;
    seen.add(fp);
    events.push({
      text: rawText,
      candidates: candidates.slice(0, 30),
      odds,
    });
    if (events.length >= 200) break;
  }
  return events;
}
"""

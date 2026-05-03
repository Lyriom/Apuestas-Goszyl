from app.scrapers.base import BaseScraper, ScrapedOdd


class EcuabetScraper(BaseScraper):
    bookmaker = 'Ecuabet'
    url = 'https://www.ecuabet.com'

    async def scrape(self) -> list[ScrapedOdd]:
        if self.settings.scrapers_use_mock:
            return await self.mock_data([(2.72, 3.18, 2.46), (2.20, 3.30, 3.05), (1.92, 3.35, 4.10)])
        return await self.extract_with_playwright(['[data-testid*=event]', '[data-qa*=event]', 'article'])

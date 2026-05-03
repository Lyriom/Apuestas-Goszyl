from app.scrapers.base import BaseScraper, ScrapedOdd


class Bet593Scraper(BaseScraper):
    bookmaker = 'Bet593'
    url = 'https://www.bet593.com'

    async def scrape(self) -> list[ScrapedOdd]:
        if self.settings.scrapers_use_mock:
            return await self.mock_data([(2.66, 3.28, 2.55), (2.26, 3.20, 3.00), (1.96, 3.25, 4.05)])
        return await self.extract_with_playwright(['[data-testid*=match]', '[data-qa*=match]', '.match'])

from app.scrapers.base import BaseScraper, ScrapedOdd


class BetcrisScraper(BaseScraper):
    bookmaker = 'Betcris'
    url = 'https://www.betcris.com.ec'

    async def scrape(self) -> list[ScrapedOdd]:
        if self.settings.scrapers_use_mock:
            return await self.mock_data([(2.85, 3.05, 2.40), (2.12, 3.45, 3.18), (1.88, 3.50, 4.20)])
        return await self.extract_with_playwright(['[data-testid*=fixture]', '[data-test*=event]', '.event'])

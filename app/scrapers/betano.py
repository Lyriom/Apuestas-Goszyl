from app.scrapers.base import BaseScraper, ScrapedOdd


class BetanoScraper(BaseScraper):
    bookmaker = 'Betano'
    url = 'https://www.betano.ec'

    async def scrape(self) -> list[ScrapedOdd]:
        if self.settings.scrapers_use_mock:
            return await self.mock_data([(2.78, 3.22, 2.50), (2.18, 3.38, 3.22), (1.90, 3.42, 4.35)])
        return await self.extract_with_playwright(['[data-qa*=event]', '[data-testid*=selection]', '.events-list__grid'])

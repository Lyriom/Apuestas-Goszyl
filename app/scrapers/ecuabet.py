from app.scrapers.base import BaseScraper, ScrapedOdd


class EcuabetScraper(BaseScraper):
    bookmaker = 'Ecuabet'
    url = 'https://www.ecuabet.com'
    tournament = 'LigaPro Ecuador'

    URLS = [
        'https://www.ecuabet.com/sports/futbol/ecuador',
        'https://www.ecuabet.com/sports/futbol/ecuador/liga-pro',
    ]

    async def scrape(self) -> list[ScrapedOdd]:
        return await self.fetch_events(self.URLS)

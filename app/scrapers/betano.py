from app.scrapers.base import BaseScraper, ScrapedOdd


class BetanoScraper(BaseScraper):
    bookmaker = 'Betano'
    url = 'https://www.betano.ec'
    tournament = 'LigaPro Ecuador'

    URLS = [
        'https://www.betano.ec/sport/futbol/ecuador/serie-a-15094/',
        'https://www.betano.ec/sport/futbol/ecuador/',
    ]

    async def scrape(self) -> list[ScrapedOdd]:
        return await self.fetch_events(self.URLS)

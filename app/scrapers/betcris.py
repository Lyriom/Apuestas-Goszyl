from app.scrapers.base import BaseScraper, ScrapedOdd


class BetcrisScraper(BaseScraper):
    bookmaker = 'Betcris'
    url = 'https://www.betcris.com.ec'
    tournament = 'LigaPro Ecuador'

    URLS = [
        'https://www.betcris.com.ec/es/apuestas-deportivas/futbol/ecuador',
        'https://www.betcris.com.ec/es/apuestas-deportivas/futbol/ecuador/serie-a',
    ]

    async def scrape(self) -> list[ScrapedOdd]:
        return await self.fetch_events(self.URLS)

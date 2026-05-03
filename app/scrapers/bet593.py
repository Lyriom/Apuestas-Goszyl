from app.scrapers.base import BaseScraper, ScrapedOdd


class Bet593Scraper(BaseScraper):
    bookmaker = 'Bet593'
    url = 'https://www.bet593.com'
    tournament = 'LigaPro Ecuador'

    URLS = [
        'https://www.bet593.com/sports/futbol/ecuador',
        'https://www.bet593.com/sports/futbol/ecuador/liga-pro',
    ]

    async def scrape(self) -> list[ScrapedOdd]:
        return await self.fetch_events(self.URLS)

"""Scraper de Pinnacle (API pública del front-end).

Pinnacle expone un API REST JSON sin autenticación que sirve fixtures y
moneylines (1X2). A diferencia de Sofascore o de los bookmakers locales
ecuatorianos, este endpoint responde desde cualquier IP sin geo-bloqueo
y sin Cloudflare. Es nuestra fuente principal de cuotas reales para la
LigaPro y para los equipos ecuatorianos en torneos internacionales.
"""
from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

import httpx
from loguru import logger

from app.scrapers.base import BaseScraper, ScrapedOdd

PINNACLE_BASE = 'https://guest.api.arcadia.pinnacle.com/0.1'
PINNACLE_API_KEY = 'CmX2KcMrXuFmNg6YFbmTxE0y9CIrOi0R'

LEAGUES = (
    (5598, 'LigaPro Ecuador'),
    (1875, 'Copa Libertadores'),
    (2472, 'Copa Sudamericana'),
    (2686, 'FIFA World Cup'),
    (2016, 'Eliminatorias Sudamericanas'),
    (1872, 'Copa America'),
)

ECUADOR_TEAM_PATTERNS = re.compile(
    r'(?:'
    r'\becuador\b|'
    r'\bldu\b|liga de quito|'
    r'barcelona sc\b|'
    r'\bemelec\b|'
    r'\baucas\b|'
    r'\borense\b|'
    r'deportivo cuenca|'
    r'\bdelfin\b|'
    r'el nacional|'
    r'libertad fc|'
    r'\bmacara\b|'
    r'mushuc runa|'
    r'tecnico universitario|'
    r'universidad catolica del ecuador|'
    r'guayaquil city|'
    r'\bmanta fc\b|'
    r'leones del norte|'
    r'\bimbabura\b|'
    r'\bvinotinto\b|'
    r'independiente del valle|'
    r'\bidv\b'
    r')',
    re.IGNORECASE,
)

HEADERS = {
    'X-API-Key': PINNACLE_API_KEY,
    'Accept': 'application/json',
    'Referer': 'https://www.pinnacle.com/',
    'Origin': 'https://www.pinnacle.com',
    'User-Agent': (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    ),
}


def _american_to_decimal(price: int | float | None) -> float | None:
    """Pinnacle entrega moneyline en formato americano (+150 / -200)."""
    if price is None:
        return None
    try:
        price = float(price)
    except (TypeError, ValueError):
        return None
    if price == 0:
        return None
    if price > 0:
        return round(price / 100 + 1, 2)
    return round(100 / abs(price) + 1, 2)


def _parse_start(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = value.replace('Z', '+00:00')
    try:
        return datetime.fromisoformat(raw).astimezone(UTC)
    except ValueError:
        return None


def _is_ecuadorian(name: str | None) -> bool:
    if not name:
        return False
    return bool(ECUADOR_TEAM_PATTERNS.search(name))


class PinnacleScraper(BaseScraper):
    bookmaker = 'Pinnacle'
    url = 'https://www.pinnacle.com'
    tournament = 'LigaPro Ecuador'

    async def scrape(self) -> list[ScrapedOdd]:
        timeout = httpx.Timeout(self.settings.scrapers_timeout_seconds)
        scraped: list[ScrapedOdd] = []
        async with httpx.AsyncClient(headers=HEADERS, timeout=timeout, follow_redirects=True) as client:
            for league_id, tournament_name in LEAGUES:
                items = await self._scrape_league(client, league_id, tournament_name)
                scraped.extend(items)
        logger.info('pinnacle_total_items={}', len(scraped))
        return scraped

    async def _scrape_league(
        self,
        client: httpx.AsyncClient,
        league_id: int,
        tournament_name: str,
    ) -> list[ScrapedOdd]:
        try:
            resp = await client.get(f'{PINNACLE_BASE}/leagues/{league_id}/matchups')
            resp.raise_for_status()
            matchups: list[dict[str, Any]] = resp.json() or []
        except httpx.HTTPError as exc:
            logger.warning('pinnacle_league_failed league={} err={}', league_id, exc)
            return []

        wanted = league_id == 5598
        results: list[ScrapedOdd] = []
        for matchup in matchups:
            if matchup.get('type') != 'matchup':
                continue
            participants = matchup.get('participants') or []
            if len(participants) < 2:
                continue
            home = next((p for p in participants if p.get('alignment') == 'home'), participants[0])
            away = next((p for p in participants if p.get('alignment') == 'away'), participants[1])
            home_name = (home or {}).get('name')
            away_name = (away or {}).get('name')
            if not home_name or not away_name:
                continue
            if not wanted and not (_is_ecuadorian(home_name) or _is_ecuadorian(away_name)):
                continue

            kickoff = _parse_start(matchup.get('startTime'))
            if not kickoff:
                continue

            home_odd, draw_odd, away_odd = await self._fetch_moneyline(client, matchup.get('id'))
            if home_odd is None and draw_odd is None and away_odd is None:
                continue

            results.append(ScrapedOdd(
                bookmaker=self.bookmaker,
                tournament=tournament_name,
                home_team=home_name,
                away_team=away_name,
                kickoff_at=kickoff,
                home_odd=home_odd,
                draw_odd=draw_odd,
                away_odd=away_odd,
            ))
        logger.info('pinnacle_league_done league={} tournament={} matches={}', league_id, tournament_name, len(results))
        return results

    async def _fetch_moneyline(
        self,
        client: httpx.AsyncClient,
        matchup_id: int | None,
    ) -> tuple[float | None, float | None, float | None]:
        if not matchup_id:
            return None, None, None
        try:
            resp = await client.get(f'{PINNACLE_BASE}/matchups/{matchup_id}/markets/related/straight')
            resp.raise_for_status()
            markets: list[dict[str, Any]] = resp.json() or []
        except httpx.HTTPError as exc:
            logger.debug('pinnacle_markets_failed matchup={} err={}', matchup_id, exc)
            return None, None, None

        full_time = next(
            (
                m for m in markets
                if m.get('type') == 'moneyline'
                and m.get('period') == 0
                and m.get('key') == 's;0;m'
            ),
            None,
        )
        if not full_time:
            return None, None, None
        prices = full_time.get('prices') or []
        by_designation: dict[str, float | None] = {}
        for entry in prices:
            designation = (entry.get('designation') or '').lower()
            if designation in {'home', 'draw', 'away'}:
                by_designation[designation] = _american_to_decimal(entry.get('price'))
        return (
            by_designation.get('home'),
            by_designation.get('draw'),
            by_designation.get('away'),
        )

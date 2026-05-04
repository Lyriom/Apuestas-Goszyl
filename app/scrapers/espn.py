"""Scraper de fixtures + escudos desde la API pública de ESPN.

ESPN no entrega cuotas pero sí calendario oficial y los logos de cada
equipo en `a.espncdn.com`. Lo corremos primero en el scheduler para
sembrar la tabla de matches con escudos; las casas de apuestas
(Ecuabet/Doradobet/Bet593) luego completan los odds sobre los partidos
ya creados — cuando los nombres dedupen, ESPN inyecta los escudos en el
mismo Match row vía `find_or_create_match`.
"""
from __future__ import annotations

import unicodedata
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from loguru import logger

from app.scrapers.base import BaseScraper, ScrapedOdd

ESPN_SCOREBOARD = (
    'https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard'
)

# (league_slug, tournament_label, requires_ecuadorian_team)
LEAGUES = (
    ('ECU.1', 'LigaPro Ecuador', False),
    ('conmebol.libertadores', 'Copa Libertadores', True),
    ('conmebol.sudamericana', 'Copa Sudamericana', True),
    ('fifa.worldq.conmebol', 'Eliminatorias Sudamericanas', True),
    ('fifa.world', 'FIFA World Cup', True),
)

ECUADOR_TEAM_KEYWORDS = (
    'ldu', 'liga de quito', 'barcelona sc', 'emelec', 'aucas', 'orense',
    'deportivo cuenca', 'cuenca', 'delfin', 'el nacional', 'libertad',
    'macara', 'mushuc runa', 'tecnico universitario', 'universidad catolica',
    'guayaquil city', 'manta', 'leones', 'imbabura', 'vinotinto',
    'independiente del valle', 'idv', 'cuniburo', 'ecuador',
)

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    ),
    'Accept': 'application/json',
    'Accept-Language': 'es-EC,es;q=0.9,en;q=0.8',
    'Referer': 'https://www.espn.com/',
}


def _norm(value: str | None) -> str:
    if not value:
        return ''
    nfd = unicodedata.normalize('NFD', str(value))
    return ''.join(c for c in nfd if unicodedata.category(c) != 'Mn').lower().strip()


def _has_ecuadorian_team(home: str, away: str) -> bool:
    blob = f' {_norm(home)} {_norm(away)} '
    return any(
        f' {k} ' in blob
        or blob.startswith(f'{k} ')
        or blob.endswith(f' {k}')
        or k in blob.split()
        for k in ECUADOR_TEAM_KEYWORDS
    )


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(UTC)
    except ValueError:
        return None


def _date_windows(now: datetime) -> list[str]:
    start = now - timedelta(days=1)
    end = now + timedelta(days=21)
    return [f'{start.strftime("%Y%m%d")}-{end.strftime("%Y%m%d")}']


class EspnScraper(BaseScraper):
    bookmaker = 'ESPN-Fixtures'
    url = 'https://www.espn.com'
    tournament = 'LigaPro Ecuador'

    async def scrape(self) -> list[ScrapedOdd]:
        timeout = httpx.Timeout(self.settings.scrapers_timeout_seconds)
        now = datetime.now(UTC)
        results: list[ScrapedOdd] = []
        async with httpx.AsyncClient(headers=HEADERS, timeout=timeout, follow_redirects=True) as client:
            for league_slug, tournament_name, requires_ec in LEAGUES:
                events = await self._fetch_events(client, league_slug, _date_windows(now))
                results.extend(self._to_scraped(events, tournament_name, requires_ec))
        logger.info('espn_total_items={}', len(results))
        return results

    async def _fetch_events(
        self,
        client: httpx.AsyncClient,
        league_slug: str,
        windows: list[str],
    ) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        for window in windows:
            try:
                resp = await client.get(
                    ESPN_SCOREBOARD.format(league=league_slug),
                    params={'dates': window, 'limit': 200},
                )
                resp.raise_for_status()
                payload = resp.json() or {}
                events.extend(payload.get('events') or [])
            except httpx.HTTPError as exc:
                logger.warning('espn_fetch_failed league={} window={} err={}', league_slug, window, exc)
        return events

    def _to_scraped(
        self,
        events: list[dict[str, Any]],
        tournament_name: str,
        requires_ec: bool,
    ) -> list[ScrapedOdd]:
        results: list[ScrapedOdd] = []
        for event in events:
            kickoff = _parse_iso(event.get('date'))
            if not kickoff:
                continue
            comp = (event.get('competitions') or [{}])[0]
            competitors = comp.get('competitors') or []
            home = next((c for c in competitors if c.get('homeAway') == 'home'), None)
            away = next((c for c in competitors if c.get('homeAway') == 'away'), None)
            if not home or not away:
                continue
            home_team = home.get('team') or {}
            away_team = away.get('team') or {}
            home_name = (home_team.get('displayName') or '').strip()
            away_name = (away_team.get('displayName') or '').strip()
            if not home_name or not away_name:
                continue
            if requires_ec and not _has_ecuadorian_team(home_name, away_name):
                continue
            results.append(ScrapedOdd(
                bookmaker=self.bookmaker,
                tournament=tournament_name,
                home_team=home_name,
                away_team=away_name,
                kickoff_at=kickoff,
                home_odd=None,
                draw_odd=None,
                away_odd=None,
                home_logo_url=home_team.get('logo') or None,
                away_logo_url=away_team.get('logo') or None,
            ))
        return results

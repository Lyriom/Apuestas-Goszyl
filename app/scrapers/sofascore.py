"""Scraper basado en la API JSON pública de Sofascore.

Sofascore expone endpoints estables para fixtures y cuotas que sirven
LigaPro Ecuador y partidos de la selección. A diferencia de los sitios
de cada bookmaker local (que geo-bloquean al server fuera de EC y son
SPAs frágiles), esta fuente responde JSON limpio desde cualquier IP.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
from loguru import logger

from app.scrapers.base import BaseScraper, ScrapedOdd

SOFASCORE_BASE = 'https://api.sofascore.com/api/v1'

LIGAPRO_TOURNAMENT_IDS = (240,)
ECUADOR_NT_TEAM_ID = 4819

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/124.0 Safari/537.36'
    ),
    'Accept': 'application/json',
    'Accept-Language': 'es-EC,es;q=0.9,en;q=0.8',
    'Referer': 'https://www.sofascore.com/',
}


def _parse_kickoff(value: int | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=UTC)
    except (ValueError, OSError):
        return None


def _fractional_to_decimal(raw: str | None) -> float | None:
    if not raw:
        return None
    raw = raw.strip()
    try:
        if '/' in raw:
            num, den = raw.split('/', 1)
            num_f = float(num.replace(',', '.'))
            den_f = float(den.replace(',', '.'))
            if den_f == 0:
                return None
            return round(num_f / den_f + 1, 2)
        return round(float(raw.replace(',', '.')), 2)
    except (ValueError, ZeroDivisionError):
        return None


class SofascoreScraper(BaseScraper):
    bookmaker = 'Sofascore'
    url = 'https://www.sofascore.com'
    tournament = 'LigaPro Ecuador'

    async def scrape(self) -> list[ScrapedOdd]:
        timeout = httpx.Timeout(self.settings.scrapers_timeout_seconds)
        async with httpx.AsyncClient(headers=HEADERS, timeout=timeout, follow_redirects=True) as client:
            events: list[dict[str, Any]] = []
            for tournament_id in LIGAPRO_TOURNAMENT_IDS:
                events.extend(await self._fetch_tournament_events(client, tournament_id))
            events.extend(await self._fetch_team_events(client, ECUADOR_NT_TEAM_ID))

            seen_ids: set[int] = set()
            unique_events: list[dict[str, Any]] = []
            for event in events:
                event_id = event.get('id')
                if not isinstance(event_id, int) or event_id in seen_ids:
                    continue
                seen_ids.add(event_id)
                unique_events.append(event)

            logger.info('sofascore_events_collected total={}', len(unique_events))

            scraped: list[ScrapedOdd] = []
            for event in unique_events:
                home = (event.get('homeTeam') or {}).get('name')
                away = (event.get('awayTeam') or {}).get('name')
                kickoff = _parse_kickoff(event.get('startTimestamp'))
                tournament_name = (
                    (event.get('tournament') or {}).get('name')
                    or self.tournament
                )
                if not home or not away or not kickoff:
                    continue
                home_odd, draw_odd, away_odd = await self._fetch_event_odds(client, event['id'])
                if home_odd is None and draw_odd is None and away_odd is None:
                    continue
                scraped.append(ScrapedOdd(
                    bookmaker=self.bookmaker,
                    tournament=tournament_name,
                    home_team=home,
                    away_team=away,
                    kickoff_at=kickoff,
                    home_odd=home_odd,
                    draw_odd=draw_odd,
                    away_odd=away_odd,
                ))
            return scraped

    async def _fetch_tournament_events(
        self, client: httpx.AsyncClient, tournament_id: int
    ) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        try:
            seasons_resp = await client.get(
                f'{SOFASCORE_BASE}/unique-tournament/{tournament_id}/seasons'
            )
            seasons_resp.raise_for_status()
            seasons = (seasons_resp.json() or {}).get('seasons') or []
        except httpx.HTTPError as exc:
            logger.warning('sofascore_seasons_failed tournament={} err={}', tournament_id, exc)
            return events
        for season in seasons[:2]:
            season_id = season.get('id')
            if not season_id:
                continue
            for path in ('next/0', 'last/0'):
                try:
                    resp = await client.get(
                        f'{SOFASCORE_BASE}/unique-tournament/{tournament_id}'
                        f'/season/{season_id}/events/{path}'
                    )
                    resp.raise_for_status()
                    events.extend((resp.json() or {}).get('events') or [])
                except httpx.HTTPError as exc:
                    logger.warning(
                        'sofascore_events_failed tournament={} season={} path={} err={}',
                        tournament_id, season_id, path, exc,
                    )
        return events

    async def _fetch_team_events(
        self, client: httpx.AsyncClient, team_id: int
    ) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        for path in ('next/0', 'last/0'):
            try:
                resp = await client.get(f'{SOFASCORE_BASE}/team/{team_id}/events/{path}')
                resp.raise_for_status()
                events.extend((resp.json() or {}).get('events') or [])
            except httpx.HTTPError as exc:
                logger.warning('sofascore_team_events_failed team={} path={} err={}', team_id, path, exc)
        return events

    async def _fetch_event_odds(
        self, client: httpx.AsyncClient, event_id: int
    ) -> tuple[float | None, float | None, float | None]:
        try:
            resp = await client.get(f'{SOFASCORE_BASE}/event/{event_id}/odds/1/all')
            resp.raise_for_status()
            payload = resp.json() or {}
        except httpx.HTTPError as exc:
            logger.debug('sofascore_odds_failed event={} err={}', event_id, exc)
            return None, None, None

        markets = payload.get('markets') or []
        full_time = next(
            (
                m for m in markets
                if (m.get('marketName') or '').lower() in {'full time', 'match winner', '1x2'}
                or m.get('marketId') == 1
            ),
            None,
        )
        if not full_time:
            return None, None, None
        choices = full_time.get('choices') or []
        odds_by_name: dict[str, float | None] = {}
        for choice in choices:
            name = (choice.get('name') or '').strip().lower()
            decimal = _fractional_to_decimal(choice.get('fractionalValue'))
            if decimal is None:
                decimal = _fractional_to_decimal(choice.get('decimalValue'))
            odds_by_name[name] = decimal
        return (
            odds_by_name.get('1') or odds_by_name.get('home'),
            odds_by_name.get('x') or odds_by_name.get('draw'),
            odds_by_name.get('2') or odds_by_name.get('away'),
        )

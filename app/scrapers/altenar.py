"""Adaptador genérico para casas de apuestas que corren sobre Altenar.

Altenar es un backend B2B usado por Ecuabet, Doradobet y Bet593 (entre
otros). Sus widgets exponen JSON sin autenticación en
`sb2frontend-altenar2.biahosted.com/api/widget/GetEvents`. Cambiando el
parámetro `integration` (`ecuabet` / `doradobet` / `bet593`) obtenemos
las cuotas reales de cada casa con su propio margen.

Inspirado en `odds-collector` (MISIVADEV) pero portado a Python con
httpx — sin Playwright, sin browser, server-side directo.
"""
from __future__ import annotations

import unicodedata
from datetime import UTC, datetime
from typing import Any

import httpx
from loguru import logger

from app.scrapers.base import BaseScraper, ScrapedOdd

ALTENAR_BASE = 'https://sb2frontend-altenar2.biahosted.com'
ALTENAR_FOOTBALL_SPORT_ID = 66
ECUADOR_CATEGORY_ID = 852

INTERNATIONAL_TOURNAMENT_KEYWORDS = (
    'libertadores',
    'sudamericana',
    'conmebol',
    'copa america',
    'eliminatorias sudamericanas',
    'world cup',
    'mundial',
)

ECUADOR_TEAM_KEYWORDS = (
    'ldu', 'liga de quito',
    'barcelona sc',
    'emelec',
    'aucas',
    'orense',
    'deportivo cuenca', 'cuenca',
    'delfin',
    'el nacional',
    'libertad',
    'macara',
    'mushuc runa',
    'tecnico universitario',
    'u. cat', 'universidad catolica del ecuador',
    'guayaquil city',
    'manta',
    'leones del norte', 'leones',
    'imbabura',
    'vinotinto',
    'independiente del valle', 'idv',
    'cuniburo',
)


def _norm(value: str | None) -> str:
    if not value:
        return ''
    nfkd = unicodedata.normalize('NFD', str(value))
    no_accents = ''.join(c for c in nfkd if unicodedata.category(c) != 'Mn')
    return no_accents.lower().strip()


def _is_international_target(name: str) -> bool:
    n = _norm(name)
    return any(k in n for k in INTERNATIONAL_TOURNAMENT_KEYWORDS)


def _has_ecuadorian_team(home: str, away: str) -> bool:
    blob = f' {_norm(home)} {_norm(away)} '
    return any(f' {k} ' in blob or blob.startswith(f'{k} ') or blob.endswith(f' {k}') or k in blob.split()
               for k in ECUADOR_TEAM_KEYWORDS)


def _parse_start(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = str(value).replace('Z', '+00:00')
    try:
        return datetime.fromisoformat(raw).astimezone(UTC)
    except ValueError:
        return None


def _safe_price(raw: Any) -> float | None:
    try:
        n = float(raw)
    except (TypeError, ValueError):
        return None
    if not (1.01 <= n <= 200):
        return None
    return round(n, 2)


def _classify_outcome(name: str, home: str, away: str) -> str | None:
    """Map an Altenar outcome name to one of {home, draw, away}."""
    n = _norm(name)
    if not n:
        return None
    if n in {'1', 'home'}:
        return 'home'
    if n in {'x', 'draw', 'empate'}:
        return 'draw'
    if n in {'2', 'away'}:
        return 'away'
    if n == _norm(home):
        return 'home'
    if n == _norm(away):
        return 'away'
    return None


class AltenarScraper(BaseScraper):
    """Subclasses provide `bookmaker`, `integration`, `referer_url` and
    optionally `bookmaker_label`.
    """

    integration: str
    referer_url: str
    culture: str = 'es-ES'
    timezone_offset: int = 300
    device_type: int = 1
    num_format: str = 'en-GB'
    country_code: str = 'EC'

    async def scrape(self) -> list[ScrapedOdd]:
        timeout = httpx.Timeout(self.settings.scrapers_timeout_seconds)
        params = {
            'culture': self.culture,
            'timezoneOffset': str(self.timezone_offset),
            'integration': self.integration,
            'deviceType': str(self.device_type),
            'numFormat': self.num_format,
            'countryCode': self.country_code,
            'sportId': str(ALTENAR_FOOTBALL_SPORT_ID),
        }
        headers = {
            'Accept': 'application/json, text/plain, */*',
            'Origin': self.referer_url.rstrip('/'),
            'Referer': self.referer_url if self.referer_url.endswith('/') else self.referer_url + '/',
            'User-Agent': (
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
                '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
            ),
        }

        async with httpx.AsyncClient(headers=headers, timeout=timeout, follow_redirects=True) as client:
            try:
                resp = await client.get(f'{ALTENAR_BASE}/api/widget/GetEvents', params=params)
                resp.raise_for_status()
                payload = resp.json() or {}
            except httpx.HTTPError as exc:
                logger.warning(
                    'altenar_get_events_failed bookmaker={} integration={} err={}',
                    self.bookmaker, self.integration, exc,
                )
                return []

        return self._extract_rows(payload)

    def _extract_rows(self, payload: dict[str, Any]) -> list[ScrapedOdd]:
        events = payload.get('events') or []
        markets_by_id = {m['id']: m for m in payload.get('markets') or [] if 'id' in m}
        odds_by_id = {o['id']: o for o in payload.get('odds') or [] if 'id' in o}
        champs_by_id = {c['id']: c.get('name', '') for c in payload.get('champs') or [] if 'id' in c}
        competitors_by_id = {c['id']: c.get('name', '') for c in payload.get('competitors') or [] if 'id' in c}

        rows: list[ScrapedOdd] = []
        for event in events:
            champ_name = champs_by_id.get(event.get('champId'), '')
            is_national = event.get('catId') == ECUADOR_CATEGORY_ID
            is_international = (not is_national) and _is_international_target(champ_name)
            if not is_national and not is_international:
                continue

            home, away = self._team_names(event, competitors_by_id)
            if not home or not away:
                continue
            if is_international and not _has_ecuadorian_team(home, away):
                continue

            kickoff = _parse_start(event.get('startDate'))
            if not kickoff or kickoff < datetime.now(UTC):
                continue

            home_odd, draw_odd, away_odd = self._h2h_odds(event, markets_by_id, odds_by_id, home, away)
            if home_odd is None and draw_odd is None and away_odd is None:
                continue

            tournament = self._normalize_tournament(champ_name)
            rows.append(ScrapedOdd(
                bookmaker=self.bookmaker,
                tournament=tournament,
                home_team=home,
                away_team=away,
                kickoff_at=kickoff,
                home_odd=home_odd,
                draw_odd=draw_odd,
                away_odd=away_odd,
            ))

        logger.info(
            'altenar_extracted bookmaker={} integration={} rows={}',
            self.bookmaker, self.integration, len(rows),
        )
        return rows

    @staticmethod
    def _team_names(
        event: dict[str, Any],
        competitors_by_id: dict[int, str],
    ) -> tuple[str, str]:
        cids = event.get('competitorIds') or []
        names = [competitors_by_id.get(cid, '') for cid in cids]
        names = [n for n in names if n]
        if len(names) >= 2:
            return names[0], names[1]
        raw_name = str(event.get('name') or '')
        for sep in (' vs. ', ' vs ', ' - '):
            if sep in raw_name:
                parts = [p.strip() for p in raw_name.split(sep, 1)]
                if len(parts) == 2 and all(parts):
                    return parts[0], parts[1]
        return '', ''

    @staticmethod
    def _h2h_odds(
        event: dict[str, Any],
        markets_by_id: dict[int, dict[str, Any]],
        odds_by_id: dict[int, dict[str, Any]],
        home: str,
        away: str,
    ) -> tuple[float | None, float | None, float | None]:
        for market_id in event.get('marketIds') or []:
            market = markets_by_id.get(market_id)
            if not market:
                continue
            market_name = _norm(market.get('name'))
            if not (
                '1x2' in market_name
                or 'ganador' in market_name
                or 'resultado' in market_name and 'tiempo' not in market_name
                or 'full time' in market_name
            ):
                continue
            home_odd = draw_odd = away_odd = None
            for odd_id in market.get('oddIds') or []:
                odd = odds_by_id.get(odd_id)
                if not odd:
                    continue
                price = _safe_price(odd.get('price'))
                if price is None:
                    continue
                slot = _classify_outcome(odd.get('name', ''), home, away)
                if slot == 'home' and home_odd is None:
                    home_odd = price
                elif slot == 'draw' and draw_odd is None:
                    draw_odd = price
                elif slot == 'away' and away_odd is None:
                    away_odd = price
            if home_odd or draw_odd or away_odd:
                return home_odd, draw_odd, away_odd
        return None, None, None

    @staticmethod
    def _normalize_tournament(raw: str) -> str:
        n = _norm(raw)
        if not n:
            return 'LigaPro Ecuador'
        if 'liga ecuabet primera a' in n or 'ligapro serie a' in n or 'liga pro league' in n or 'liga pro' in n:
            return 'LigaPro Ecuador'
        if 'primera b' in n:
            return 'LigaPro Serie B'
        if 'libertadores' in n:
            return 'Copa Libertadores'
        if 'sudamericana' in n:
            return 'Copa Sudamericana'
        if 'copa ecuador' in n:
            return 'Copa Ecuador'
        if 'world cup' in n or 'mundial' in n:
            return 'FIFA World Cup'
        if 'eliminator' in n:
            return 'Eliminatorias Sudamericanas'
        if 'copa america' in n:
            return 'Copa America'
        return raw.strip() or 'LigaPro Ecuador'


class EcuabetScraper(AltenarScraper):
    bookmaker = 'Ecuabet'
    url = 'https://ecuabet.com'
    integration = 'ecuabet'
    referer_url = 'https://ecuabet.com/'


class DoradobetScraper(AltenarScraper):
    bookmaker = 'Doradobet'
    url = 'https://doradobet.com'
    integration = 'doradobet'
    referer_url = 'https://doradobet.com/'


class Bet593Scraper(AltenarScraper):
    bookmaker = 'Bet593'
    url = 'https://www.bet593.com'
    integration = 'bet593'
    referer_url = 'https://www.bet593.com/'

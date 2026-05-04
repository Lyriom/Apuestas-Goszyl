"""Stub de scraper para Betano.

Betano corre sobre Kaizen Gaming, no sobre Altenar, y aplica protección
Cloudflare agresiva contra requests server-side directos. Lo dejamos
como stub para que aparezca en el panel admin y monitoreemos cuándo
empieza a fallar/funcionar — la integración real requiere Playwright +
fingerprinting de browser y se evaluará por separado.
"""
from __future__ import annotations

import httpx
from loguru import logger

from app.scrapers.base import BaseScraper, ScrapedOdd

BETANO_PROBE_URL = 'https://www.betano.com/sport/futbol/ecuador-1170/'

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    ),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'es-EC,es;q=0.9,en;q=0.8',
}


class BetanoScraper(BaseScraper):
    """Probe-only: Betano front bloquea con Cloudflare desde server. La
    corrida hace una petición HEAD para registrar el bloqueo y queda en
    el log como 'error'; permite ver cuándo abren tráfico server-side.
    """

    bookmaker = 'Betano'
    url = 'https://www.betano.com'
    tournament = 'LigaPro Ecuador'

    async def scrape(self) -> list[ScrapedOdd]:
        timeout = httpx.Timeout(self.settings.scrapers_timeout_seconds)
        async with httpx.AsyncClient(headers=HEADERS, timeout=timeout, follow_redirects=True) as client:
            try:
                resp = await client.get(BETANO_PROBE_URL)
                if resp.status_code == 200 and 'Betano' in resp.text and 'Splash' not in resp.text:
                    logger.warning(
                        'betano_unexpected_open status={} — front loaded server-side, integration pending',
                        resp.status_code,
                    )
                else:
                    raise RuntimeError(
                        f'Betano blocked: HTTP {resp.status_code} (Cloudflare/Splash). '
                        'Integration requires browser automation.'
                    )
            except httpx.HTTPError as exc:
                raise RuntimeError(f'Betano probe failed: {exc}') from exc
        return []

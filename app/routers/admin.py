import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from loguru import logger
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.database import get_db
from app.templating import templates
from app.models import Match, Odd
from app.scrapers.scheduler import BOOKMAKER_SCRAPERS, SCRAPER_CLASSES, run_scraper
from app.services.featured_service import count_featured, list_featured
from app.services.match_service import count_upcoming_matches
from app.services.odd_service import all_raw_odds, count_odds_today
from app.services.scrape_log_service import all_logs, latest_logs

router = APIRouter(prefix='/admin', tags=['admin'], dependencies=[Depends(require_admin)])


@router.get('', response_class=HTMLResponse)
async def dashboard(request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    return templates.TemplateResponse(request, 'admin/dashboard.html', {
        'latest_logs': await latest_logs(db),
        'upcoming_count': await count_upcoming_matches(db),
        'odds_today': await count_odds_today(db),
        'featured_count': await count_featured(db),
    })


@router.get('/scrapers', response_class=HTMLResponse)
async def scrapers(request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    return templates.TemplateResponse(request, 'admin/scrapers.html', {'scrapers': BOOKMAKER_SCRAPERS, 'latest_logs': await latest_logs(db), 'logs': await all_logs(db)})


@router.post('/scrapers/{name}/run', response_class=HTMLResponse)
async def run_scraper_now(name: str, request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    if name not in SCRAPER_CLASSES:
        return HTMLResponse('<span class="text-red-500">Scraper inválido</span>', status_code=404)
    saved = await run_scraper(name)
    logger.info('manual_scraper_run name={} saved={}', name, saved)
    return templates.TemplateResponse(request, 'partials/scraper_status.html', {'name': name, 'saved': saved, 'latest_logs': await latest_logs(db)})


@router.get('/matches', response_class=HTMLResponse)
async def matches(request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    rows = list((await db.scalars(select(Match).order_by(Match.kickoff_at.asc()))).all())
    odds = await all_raw_odds(db)
    return templates.TemplateResponse(request, 'admin/matches.html', {'matches': rows, 'odds': odds})


@router.post('/matches/purge', response_class=HTMLResponse)
async def purge_matches(request: Request, db: AsyncSession = Depends(get_db)) -> RedirectResponse:
    odds_deleted = await db.execute(delete(Odd))
    matches_deleted = await db.execute(delete(Match))
    await db.commit()
    logger.warning(
        'admin_purge_matches odds={} matches={}',
        odds_deleted.rowcount,
        matches_deleted.rowcount,
    )
    return RedirectResponse('/admin/matches', status_code=303)


@router.get('/featured', response_class=HTMLResponse)
async def featured(request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    return templates.TemplateResponse(request, 'admin/featured.html', {'items': await list_featured(db)})


@router.get('/diag', response_class=JSONResponse)
async def diag(db: AsyncSession = Depends(get_db)) -> JSONResponse:
    """Connectivity probe from inside the container — verifies which
    upstream APIs the EasyPanel egress IP can actually reach. Use this
    before debugging "scrapers return 0 items" issues.
    """
    probes = [
        ('altenar_ecuabet', 'https://sb2frontend-altenar2.biahosted.com/api/widget/GetEvents?culture=es-ES&timezoneOffset=300&integration=ecuabet&deviceType=1&numFormat=en-GB&countryCode=EC&sportId=66', {'Origin': 'https://ecuabet.com', 'Referer': 'https://ecuabet.com/'}),
        ('altenar_doradobet', 'https://sb2frontend-altenar2.biahosted.com/api/widget/GetEvents?culture=es-ES&timezoneOffset=300&integration=doradobet&deviceType=1&numFormat=en-GB&countryCode=EC&sportId=66', {'Origin': 'https://doradobet.com', 'Referer': 'https://doradobet.com/'}),
        ('altenar_bet593', 'https://sb2frontend-altenar2.biahosted.com/api/widget/GetEvents?culture=es-ES&timezoneOffset=300&integration=bet593&deviceType=1&numFormat=en-GB&countryCode=EC&sportId=66', {'Origin': 'https://www.bet593.com', 'Referer': 'https://www.bet593.com/'}),
        ('espn_ligapro', 'https://site.api.espn.com/apis/site/v2/sports/soccer/ECU.1/scoreboard', {}),
        ('espn_logo', 'https://a.espncdn.com/i/teamlogos/soccer/500/2686.png', {}),
        ('betano_probe', 'https://www.betano.com/sport/futbol/ecuador-1170/', {}),
    ]
    results = []
    headers_base = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36',
        'Accept': '*/*',
    }
    async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
        for name, url, extra in probes:
            try:
                resp = await client.get(url, headers={**headers_base, **extra})
                size = len(resp.content)
                ok = 200 <= resp.status_code < 400
                results.append({
                    'probe': name,
                    'status': resp.status_code,
                    'bytes': size,
                    'ok': ok,
                })
            except Exception as exc:  # noqa: BLE001
                results.append({'probe': name, 'status': 0, 'bytes': 0, 'ok': False, 'error': str(exc)[:200]})

    schema_version = await db.scalar(text('SELECT version_num FROM alembic_version LIMIT 1'))
    has_logo_col = await db.scalar(text(
        "SELECT 1 FROM information_schema.columns WHERE table_name='matches' AND column_name='home_logo_url'"
    ))
    return JSONResponse({
        'schema_version': schema_version,
        'home_logo_url_column_present': bool(has_logo_col),
        'configured_scrapers': list(SCRAPER_CLASSES.keys()),
        'connectivity': results,
    })

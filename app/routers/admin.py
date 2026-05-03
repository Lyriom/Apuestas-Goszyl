from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_login
from app.database import get_db
from app.templating import templates
from app.models import Match
from app.scrapers.scheduler import SCRAPER_CLASSES, run_scraper
from app.services.featured_service import count_featured, list_featured
from app.services.match_service import count_upcoming_matches
from app.services.odd_service import all_raw_odds, count_odds_today
from app.services.scrape_log_service import all_logs, latest_logs

router = APIRouter(prefix='/admin', tags=['admin'], dependencies=[Depends(require_login)])


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
    return templates.TemplateResponse(request, 'admin/scrapers.html', {'scrapers': SCRAPER_CLASSES.keys(), 'latest_logs': await latest_logs(db), 'logs': await all_logs(db)})


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


@router.get('/featured', response_class=HTMLResponse)
async def featured(request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    return templates.TemplateResponse(request, 'admin/featured.html', {'items': await list_featured(db)})

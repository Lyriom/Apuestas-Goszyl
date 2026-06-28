from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.templating import templates
from app.services.featured_service import get_featured_by_slug, list_featured
from app.services.match_service import get_upcoming_matches
from app.services.odd_service import bookmaker_url, comparison_rows, known_bookmakers, latest_odds_for_match

router = APIRouter()


@router.get('/healthz')
async def healthz() -> dict[str, str]:
    return {'status': 'ok'}


@router.get('/sitemap.xml')
async def sitemap() -> Response:
    xml = '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://apuestas.gozsyl.cloud/</loc></url></urlset>'
    return Response(xml, media_type='application/xml')


@router.get('/', response_class=HTMLResponse)
async def home(request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    matches = await get_upcoming_matches(db)
    rows = await comparison_rows(db, matches)
    bookmakers = await known_bookmakers(db)
    featured = await list_featured(db)
    return templates.TemplateResponse(request, 'public/home.html', {'rows': rows, 'bookmakers': bookmakers, 'featured': featured})


@router.get('/destacado/{slug}', response_class=HTMLResponse)
async def featured_detail(slug: str, request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    item = await get_featured_by_slug(db, slug)
    if not item:
        raise HTTPException(status_code=404, detail='Contenido no encontrado')
    return templates.TemplateResponse(request, 'public/featured_detail.html', {'item': item})


@router.get('/partials/odds-table', response_class=HTMLResponse)
async def odds_table_partial(request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    matches = await get_upcoming_matches(db)
    rows = await comparison_rows(db, matches)
    return templates.TemplateResponse(request, 'partials/odds_row.html', {'rows': rows})


@router.get('/partido/{match_id}', response_class=HTMLResponse)
async def match_detail(match_id: int, request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    from app.models import Match, Odd
    from sqlalchemy import desc, select

    match = await db.get(Match, match_id)
    if not match:
        raise HTTPException(status_code=404, detail='Partido no encontrado')
    latest = await latest_odds_for_match(db, match_id)
    history = list((await db.scalars(select(Odd).where(Odd.match_id == match_id).order_by(desc(Odd.captured_at)).limit(120))).all())
    bookmaker_links = {odd.bookmaker: bookmaker_url(odd.bookmaker) for odd in latest}
    return templates.TemplateResponse(request, 'public/match_detail.html', {
        'match': match,
        'latest': latest,
        'history': history,
        'bookmaker_links': bookmaker_links,
    })

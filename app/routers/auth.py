from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.keycloak import clear_session, handle_callback, keycloak_logout_url, login_redirect
from app.config import get_settings
from app.database import get_db
from app.templating import templates

router = APIRouter(prefix='/auth', tags=['auth'])


@router.get('/login')
async def login(request: Request):
    return await login_redirect(request)


@router.get('/callback')
async def callback(request: Request, db: AsyncSession = Depends(get_db)) -> RedirectResponse:
    user = await handle_callback(request, db)
    settings = get_settings()
    if user.has_role('admin') or settings.is_admin_email(user.email):
        return RedirectResponse('/admin', status_code=303)
    return RedirectResponse('/auth/no-access', status_code=303)


@router.get('/no-access', response_class=HTMLResponse)
async def no_access(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, 'public/no_access.html', {})


@router.get('/logout')
async def logout(request: Request) -> RedirectResponse:
    id_token = request.session.get('id_token')
    clear_session(request)
    logout_url = await keycloak_logout_url(id_token)
    return RedirectResponse(logout_url or '/', status_code=303)

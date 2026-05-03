from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.keycloak import clear_session, handle_callback, login_redirect
from app.database import get_db

router = APIRouter(prefix='/auth', tags=['auth'])


@router.get('/login')
async def login(request: Request):
    return await login_redirect(request)


@router.get('/callback')
async def callback(request: Request, db: AsyncSession = Depends(get_db)) -> RedirectResponse:
    await handle_callback(request, db)
    return RedirectResponse('/admin', status_code=303)


@router.get('/logout')
async def logout(request: Request) -> RedirectResponse:
    clear_session(request)
    return RedirectResponse('/', status_code=303)

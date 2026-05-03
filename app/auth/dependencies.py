import secrets
from collections.abc import Callable

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models import User


async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User | None:
    user_id = request.session.get('user_id')
    if not user_id:
        return None
    return await db.get(User, int(user_id))


async def require_login(user: User | None = Depends(get_current_user)) -> User:
    if user is None:
        raise HTTPException(status_code=status.HTTP_307_TEMPORARY_REDIRECT, headers={'Location': '/auth/login'})
    return user


def require_role(*roles: str) -> Callable[[User], User]:
    async def dependency(user: User = Depends(require_login)) -> User:
        if not user.has_role(*roles):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='No tienes permisos para acceder a esta sección')
        return user

    return dependency


def require_api_key(authorization: str | None = Header(default=None)) -> None:
    settings = get_settings()
    if not authorization or not authorization.lower().startswith('bearer '):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='API key requerida')
    token = authorization.split(' ', 1)[1].strip()
    if not secrets.compare_digest(token, settings.sistema_a_api_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='API key inválida')

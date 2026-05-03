from typing import Any

from authlib.integrations.starlette_client import OAuth
from fastapi import Request
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.models import User

oauth = OAuth()
_registered = False


def configure_oauth(settings: Settings | None = None) -> None:
    global _registered
    if _registered:
        return
    settings = settings or get_settings()
    oauth.register(
        name='keycloak',
        server_metadata_url=settings.oidc_discovery_url,
        client_id=settings.keycloak_client_id,
        client_secret=settings.keycloak_client_secret,
        client_kwargs={'scope': 'openid email profile'},
    )
    _registered = True


def extract_roles(claims: dict[str, Any]) -> list[str]:
    realm_roles = claims.get('realm_access', {}).get('roles', [])
    resource_access = claims.get('resource_access', {})
    client_roles: list[str] = []
    for client in resource_access.values():
        client_roles.extend(client.get('roles', []))
    return sorted(set([*realm_roles, *client_roles]))


async def login_redirect(request: Request):
    configure_oauth()
    settings = get_settings()
    return await oauth.keycloak.authorize_redirect(request, settings.keycloak_redirect_uri)


async def handle_callback(request: Request, db: AsyncSession) -> User:
    configure_oauth()
    token = await oauth.keycloak.authorize_access_token(request)
    claims = token.get('userinfo') or await oauth.keycloak.userinfo(token=token)
    roles = extract_roles(dict(claims))
    keycloak_id = claims.get('sub')
    email = claims.get('email')
    if not keycloak_id or not email:
        raise ValueError('Keycloak no devolvió sub/email')

    user = await db.scalar(select(User).where(User.keycloak_id == keycloak_id))
    if user is None:
        user = User(keycloak_id=keycloak_id, email=email, name=claims.get('name') or email, roles=roles)
        db.add(user)
    else:
        user.email = email
        user.name = claims.get('name') or email
        user.roles = roles
    await db.commit()
    request.session['user_id'] = user.id
    request.session['roles'] = roles
    logger.info('user_logged_in email={} roles={}', email, roles)
    return user


def clear_session(request: Request) -> None:
    request.session.clear()

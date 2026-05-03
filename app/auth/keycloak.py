import base64
import json
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


def decode_jwt_claims(token: str | None) -> dict[str, Any]:
    if not token:
        return {}
    parts = token.split('.')
    if len(parts) < 2:
        return {}
    payload = parts[1]
    payload += '=' * (-len(payload) % 4)
    try:
        return json.loads(base64.urlsafe_b64decode(payload).decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        logger.warning('keycloak_token_decode_failed')
        return {}


def extract_roles(*claims_sets: dict[str, Any]) -> list[str]:
    roles: list[str] = []
    seen: set[str] = set()

    def add(role: Any) -> None:
        if not isinstance(role, str):
            return
        normalized = role.strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            roles.append(normalized)

    def add_from_claims(claims: dict[str, Any]) -> None:
        for role in claims.get('roles', []):
            add(role)
        for role in claims.get('realm_access', {}).get('roles', []):
            add(role)
        resource_access = claims.get('resource_access', {})
        for client in resource_access.values():
            for role in client.get('roles', []):
                add(role)

    for claims in claims_sets:
        add_from_claims(claims)
    return sorted(roles)


def merged_claims(*claims_sets: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for claims in claims_sets:
        merged.update({key: value for key, value in claims.items() if value is not None})
    return merged


async def login_redirect(request: Request):
    configure_oauth()
    settings = get_settings()
    return await oauth.keycloak.authorize_redirect(request, settings.keycloak_redirect_uri)


async def handle_callback(request: Request, db: AsyncSession) -> User:
    configure_oauth()
    settings = get_settings()
    token = await oauth.keycloak.authorize_access_token(request)
    userinfo = dict(token.get('userinfo') or await oauth.keycloak.userinfo(token=token))
    access_claims = decode_jwt_claims(token.get('access_token'))
    id_claims = decode_jwt_claims(token.get('id_token'))
    claims = merged_claims(access_claims, id_claims, userinfo)
    roles = extract_roles(access_claims, id_claims, userinfo)
    keycloak_id = claims.get('sub')
    email = claims.get('email')
    if not keycloak_id or not email:
        raise ValueError('Keycloak no devolvió sub/email')

    if settings.is_admin_email(email) and 'admin' not in {r.lower() for r in roles}:
        roles = sorted({*roles, 'admin'})

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
    request.session['email'] = email
    logger.info('user_logged_in email={} roles={}', email, roles)
    return user


def clear_session(request: Request) -> None:
    request.session.clear()

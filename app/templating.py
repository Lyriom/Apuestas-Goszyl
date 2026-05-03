from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates

from app.config import get_settings


def _session_context(request: Request) -> dict:
    settings = get_settings()
    session = getattr(request, 'session', {}) or {}
    email = session.get('email')
    roles = session.get('roles') or []
    is_admin = 'admin' in {role.lower() for role in roles} or settings.is_admin_email(email)
    return {
        'session_email': email,
        'session_roles': roles,
        'is_admin': is_admin,
        'is_authenticated': bool(session.get('user_id')),
        'app_name': settings.app_name,
    }


templates = Jinja2Templates(
    directory=str(Path(__file__).parent / 'templates'),
    context_processors=[_session_context],
)

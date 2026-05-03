from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger
from starlette.middleware.sessions import SessionMiddleware

from app.auth.keycloak import configure_oauth
from app.config import get_settings
from app.logging_setup import setup_logging
from app.routers import admin, api_internal, auth, public
from app.scrapers.scheduler import create_scheduler
from app.services.seed import seed_mock_if_empty

settings = get_settings()
setup_logging(settings.log_level)
configure_oauth(settings)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await seed_mock_if_empty()
    scheduler = create_scheduler()
    scheduler.start()
    logger.info('scheduler_started jobs={}', len(scheduler.get_jobs()))
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)
        logger.info('scheduler_stopped')


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, description=settings.app_description, version='1.0.0', lifespan=lifespan)
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        session_cookie=settings.session_cookie_name,
        https_only=settings.environment == 'production',
        same_site='lax',
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(settings.app_url).rstrip('/')],
        allow_credentials=True,
        allow_methods=['GET', 'POST', 'OPTIONS'],
        allow_headers=['Authorization', 'Content-Type', 'HX-Request'],
    )
    app.mount('/static', StaticFiles(directory='app/static'), name='static')
    app.include_router(public.router)
    app.include_router(auth.router)
    app.include_router(admin.router)
    app.include_router(api_internal.router)
    return app


app = create_app()

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_api_key
from app.database import get_db
from app.schemas.featured import FeaturedContentEncryptedIn
from app.services.featured_service import decrypt_and_save
from app.services.vault_service import VaultDecryptError

router = APIRouter(prefix='/api/internal', tags=['internal'])


@router.post('/featured-content')
async def receive_featured_content(
    payload: FeaturedContentEncryptedIn,
    _: None = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    try:
        featured = await decrypt_and_save(db, post_id=payload.post_id, ciphertext=payload.ciphertext)
        await db.commit()
        logger.info('featured_content_received post_id={}', payload.post_id)
        return {'status': 'ok', 'id': featured.post_id}
    except VaultDecryptError as exc:
        await db.rollback()
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        await db.rollback()
        logger.exception('featured_content_save_failed post_id={}', payload.post_id)
        raise HTTPException(status_code=500, detail='No se pudo guardar el contenido') from exc

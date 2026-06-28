import bleach
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FeaturedContent
from app.schemas.featured import FeaturedPlaintext
from app.services.vault_service import VaultService

ALLOWED_TAGS = bleach.sanitizer.ALLOWED_TAGS | {'p', 'br', 'h2', 'h3', 'ul', 'ol', 'li', 'strong', 'em'}
ALLOWED_ATTRS = {'a': ['href', 'title', 'rel', 'target']}


async def decrypt_and_save(db: AsyncSession, *, post_id: str, ciphertext: str, vault: VaultService | None = None) -> FeaturedContent:
    vault_service = vault or VaultService()
    payload = FeaturedPlaintext.model_validate(vault_service.decrypt_json(ciphertext))
    clean_html = bleach.clean(payload.content_html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)

    existing = await db.scalar(select(FeaturedContent).where(FeaturedContent.post_id == post_id))
    if existing:
        existing.title = payload.title
        existing.excerpt = payload.excerpt
        existing.content_html = clean_html
        existing.slug = payload.slug
        await db.flush()
        return existing

    featured = FeaturedContent(
        post_id=post_id,
        title=payload.title,
        excerpt=payload.excerpt,
        content_html=clean_html,
        slug=payload.slug,
    )
    db.add(featured)
    await db.flush()
    return featured


async def list_featured(db: AsyncSession) -> list[FeaturedContent]:
    return list((await db.scalars(select(FeaturedContent).order_by(FeaturedContent.received_at.desc()))).all())


async def get_featured_by_slug(db: AsyncSession, slug: str) -> FeaturedContent | None:
    return await db.scalar(select(FeaturedContent).where(FeaturedContent.slug == slug))


async def count_featured(db: AsyncSession) -> int:
    return len(await list_featured(db))

from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class FeaturedContent(Base):
    __tablename__ = 'featured_content'

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(240))
    excerpt: Mapped[str] = mapped_column(Text)
    content_html: Mapped[str] = mapped_column(Text)
    slug: Mapped[str] = mapped_column(String(260), index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

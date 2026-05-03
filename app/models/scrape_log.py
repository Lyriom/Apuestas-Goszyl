from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ScrapeLog(Base):
    __tablename__ = 'scrape_logs'

    id: Mapped[int] = mapped_column(primary_key=True)
    bookmaker: Mapped[str] = mapped_column(String(40), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(24), index=True)
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    items_count: Mapped[int] = mapped_column(Integer, default=0)

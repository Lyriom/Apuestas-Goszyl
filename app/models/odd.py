from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Odd(Base):
    __tablename__ = 'odds'

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey('matches.id', ondelete='CASCADE'), index=True)
    bookmaker: Mapped[str] = mapped_column(String(40), index=True)
    home_odd: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    draw_odd: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    away_odd: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    match = relationship('Match', back_populates='odds')

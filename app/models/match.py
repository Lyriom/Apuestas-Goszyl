from datetime import datetime

from sqlalchemy import DateTime, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Match(Base):
    __tablename__ = 'matches'
    __table_args__ = (UniqueConstraint('tournament', 'home_team', 'away_team', 'kickoff_at', name='uq_match_identity'),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tournament: Mapped[str] = mapped_column(String(80), index=True)
    home_team: Mapped[str] = mapped_column(String(160), index=True)
    away_team: Mapped[str] = mapped_column(String(160), index=True)
    kickoff_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(32), default='scheduled', index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    odds = relationship('Odd', back_populates='match', cascade='all, delete-orphan')

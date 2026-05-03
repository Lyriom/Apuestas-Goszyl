from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class MatchRead(BaseModel):
    id: int
    tournament: str
    home_team: str
    away_team: str
    kickoff_at: datetime
    status: str

    model_config = {'from_attributes': True}


class BestOdd(BaseModel):
    bookmaker: str | None = None
    value: Decimal | None = None


class MatchComparison(BaseModel):
    match: MatchRead
    best_home: BestOdd = Field(default_factory=BestOdd)
    best_draw: BestOdd = Field(default_factory=BestOdd)
    best_away: BestOdd = Field(default_factory=BestOdd)

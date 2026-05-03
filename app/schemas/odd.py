from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class OddRead(BaseModel):
    id: int
    match_id: int
    bookmaker: str
    home_odd: Decimal | None
    draw_odd: Decimal | None
    away_odd: Decimal | None
    captured_at: datetime

    model_config = {'from_attributes': True}

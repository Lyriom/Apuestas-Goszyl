from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import desc, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Match, Odd

BOOKMAKER_HOMEPAGE = {
    'Ecuabet': 'https://ecuabet.com/deportes',
    'Doradobet': 'https://doradobet.com/deportes',
    'Bet593': 'https://www.bet593.com/sports/futbol/ecuador',
    'Betano': 'https://www.betano.com/sport/futbol/ecuador-1170/',
}


def bookmaker_url(name: str | None) -> str | None:
    if not name:
        return None
    return BOOKMAKER_HOMEPAGE.get(name)


def _decimal(value: float | Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value)).quantize(Decimal('0.01'))


async def create_odd(
    db: AsyncSession,
    *,
    match_id: int,
    bookmaker: str,
    home_odd: float | Decimal | None,
    draw_odd: float | Decimal | None,
    away_odd: float | Decimal | None,
) -> Odd:
    odd = Odd(
        match_id=match_id,
        bookmaker=bookmaker,
        home_odd=_decimal(home_odd),
        draw_odd=_decimal(draw_odd),
        away_odd=_decimal(away_odd),
        captured_at=datetime.now(UTC),
    )
    db.add(odd)
    await db.flush()
    return odd


async def known_bookmakers(db: AsyncSession) -> list[str]:
    rows = await db.scalars(select(distinct(Odd.bookmaker)).order_by(Odd.bookmaker))
    return [name for name in rows.all() if name]


async def latest_odds_for_match(db: AsyncSession, match_id: int) -> list[Odd]:
    bookmakers = await known_bookmakers(db)
    rows: list[Odd] = []
    for bookmaker in bookmakers:
        stmt = (
            select(Odd)
            .where(Odd.match_id == match_id, Odd.bookmaker == bookmaker)
            .order_by(desc(Odd.captured_at))
            .limit(1)
        )
        odd = await db.scalar(stmt)
        if odd:
            rows.append(odd)
    return rows


async def best_odd_per_outcome(
    db: AsyncSession, match_id: int,
) -> dict[str, tuple[str | None, Decimal | None, str | None]]:
    odds = await latest_odds_for_match(db, match_id)
    result: dict[str, tuple[str | None, Decimal | None, str | None]] = {}
    for attr, key in [('home_odd', 'home'), ('draw_odd', 'draw'), ('away_odd', 'away')]:
        valid = [(odd.bookmaker, getattr(odd, attr)) for odd in odds if getattr(odd, attr) is not None]
        if valid:
            book, value = max(valid, key=lambda item: item[1])
            result[key] = (book, value, bookmaker_url(book))
        else:
            result[key] = (None, None, None)
    return result


async def comparison_rows(db: AsyncSession, matches: list[Match]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for match in matches:
        odds = await latest_odds_for_match(db, match.id)
        best = await best_odd_per_outcome(db, match.id)
        rows.append({'match': match, 'odds': odds, 'best': best})
    return rows


async def count_odds_today(db: AsyncSession) -> int:
    since = datetime.now(UTC) - timedelta(hours=24)
    return int(await db.scalar(select(func.count(Odd.id)).where(Odd.captured_at >= since)) or 0)


async def all_raw_odds(db: AsyncSession, limit: int = 200) -> list[Odd]:
    return list((await db.scalars(select(Odd).order_by(desc(Odd.captured_at)).limit(limit))).all())

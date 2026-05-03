from datetime import UTC, datetime, timedelta

from slugify import slugify
from sqlalchemy import Select, and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Match

TARGET_KEYWORDS = {'ligapro', 'ecuador', 'la tri', 'seleccion ecuador', 'selección ecuador'}


def normalize_team(value: str) -> str:
    return slugify(value or '', separator=' ')


def is_target_tournament(tournament: str) -> bool:
    normalized = normalize_team(tournament)
    return any(keyword.replace('ó', 'o') in normalized for keyword in TARGET_KEYWORDS)


async def get_upcoming_matches(db: AsyncSession, days: int = 14) -> list[Match]:
    now = datetime.now(UTC)
    stmt = (
        select(Match)
        .where(and_(Match.kickoff_at >= now, Match.kickoff_at <= now + timedelta(days=days), Match.status == 'scheduled'))
        .order_by(Match.kickoff_at.asc())
    )
    return list((await db.scalars(stmt)).all())


async def count_upcoming_matches(db: AsyncSession) -> int:
    return len(await get_upcoming_matches(db))


async def find_or_create_match(
    db: AsyncSession,
    *,
    tournament: str,
    home_team: str,
    away_team: str,
    kickoff_at: datetime,
) -> Match:
    lower = kickoff_at - timedelta(hours=8)
    upper = kickoff_at + timedelta(hours=8)
    stmt: Select[tuple[Match]] = select(Match).where(
        Match.kickoff_at.between(lower, upper),
        Match.status == 'scheduled',
    )
    candidates = list((await db.scalars(stmt)).all())
    home_norm = normalize_team(home_team)
    away_norm = normalize_team(away_team)
    for match in candidates:
        if normalize_team(match.home_team) == home_norm and normalize_team(match.away_team) == away_norm:
            return match

    match = Match(tournament=tournament, home_team=home_team, away_team=away_team, kickoff_at=kickoff_at)
    db.add(match)
    await db.flush()
    return match

from datetime import UTC, datetime, timedelta

from slugify import slugify
from sqlalchemy import Select, and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Match

TARGET_KEYWORDS = {
    'ligapro',
    'liga pro',
    'ecuador',
    'la tri',
    'seleccion ecuador',
    'selección ecuador',
    'serie a',
    'primera a',
    'primera categoria',
    'copa ecuador',
    'copa libertadores',
    'copa sudamericana',
    'fifa world cup',
    'world cup',
    'copa america',
    'eliminatorias',
    'eliminatorias sudamericanas',
}


_TEAM_SUFFIX_TOKENS = {'fc', 'sc', 'cf', 'club', 'c', 'f'}
_TEAM_ALIASES = {
    'leones': 'leones del norte',
    'idv': 'independiente del valle',
    'ldu quito': 'ldu',
    'liga de quito': 'ldu',
}


def normalize_team(value: str) -> str:
    base = slugify(value or '', separator=' ').strip()
    if not base:
        return base
    tokens = base.split()
    while len(tokens) > 1 and tokens[-1] in _TEAM_SUFFIX_TOKENS:
        tokens.pop()
    cleaned = ' '.join(tokens)
    return _TEAM_ALIASES.get(cleaned, cleaned)


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
    home_logo_url: str | None = None,
    away_logo_url: str | None = None,
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
            if home_logo_url and not match.home_logo_url:
                match.home_logo_url = home_logo_url
            if away_logo_url and not match.away_logo_url:
                match.away_logo_url = away_logo_url
            return match

    match = Match(
        tournament=tournament,
        home_team=home_team,
        away_team=away_team,
        kickoff_at=kickoff_at,
        home_logo_url=home_logo_url,
        away_logo_url=away_logo_url,
    )
    db.add(match)
    await db.flush()
    return match

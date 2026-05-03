"""Convierte los nodos crudos extraídos del DOM en eventos 1X2 estructurados."""
from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Iterable

VS_PATTERN = re.compile(r'(.+?)\s*(?:\bvs?\b|\bv\b|\s-\s|\s–\s|\s—\s)\s*(.+)', re.IGNORECASE)
TIME_PATTERN = re.compile(r'\b(\d{1,2}):(\d{2})\b')
DATE_PATTERN = re.compile(r'\b(\d{1,2})[/\-.](\d{1,2})(?:[/\-.](\d{2,4}))?\b')

NOISE_TOKENS = {
    'live', 'en vivo', 'directo', 'destacado', 'pronto', 'hoy', 'mañana',
    'apostar', 'apuesta', 'cuotas', 'cuota', 'mercados', 'ver más', 'ver mas',
    '+', '...', '·', '|', '1x2', 'ganador', 'resultado',
}


def _clean(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip()


def _looks_like_team(text: str) -> bool:
    cleaned = _clean(text)
    if not cleaned or len(cleaned) < 3 or len(cleaned) > 60:
        return False
    if cleaned.lower() in NOISE_TOKENS:
        return False
    if not re.search(r'[A-Za-zÁÉÍÓÚÑáéíóúñ]', cleaned):
        return False
    if re.fullmatch(r'\d+[.,]\d{2}', cleaned):
        return False
    return True


def _extract_teams(candidates: Iterable[str], full_text: str) -> tuple[str, str] | None:
    text_match = VS_PATTERN.search(full_text)
    if text_match:
        home = _clean(text_match.group(1).split('\n')[-1])
        away = _clean(text_match.group(2).split('\n')[0])
        if _looks_like_team(home) and _looks_like_team(away):
            return home, away

    teams = [_clean(c) for c in candidates if _looks_like_team(c)]
    deduped: list[str] = []
    for team in teams:
        if team not in deduped:
            deduped.append(team)
    if len(deduped) >= 2:
        return deduped[0], deduped[1]
    return None


def _extract_kickoff(text: str, default_kickoff: datetime) -> datetime:
    now = datetime.now(UTC)
    base = default_kickoff
    date_match = DATE_PATTERN.search(text)
    if date_match:
        day, month = int(date_match.group(1)), int(date_match.group(2))
        year_raw = date_match.group(3)
        year = now.year
        if year_raw:
            year = int(year_raw)
            if year < 100:
                year += 2000
        try:
            base = base.replace(year=year, month=month, day=day)
        except ValueError:
            pass
    time_match = TIME_PATTERN.search(text)
    if time_match:
        hour, minute = int(time_match.group(1)), int(time_match.group(2))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            base = base.replace(hour=hour, minute=minute)
    if base < now:
        base = base + timedelta(days=1)
    return base


def parse_events_from_dom(raw_events: list[dict], *, default_kickoff: datetime) -> list[dict]:
    out: list[dict] = []
    for event in raw_events:
        odds = event.get('odds') or []
        if len(odds) < 3:
            continue
        home_odd, draw_odd, away_odd = odds[0], odds[1], odds[2]
        if not (1.01 <= home_odd <= 99 and 1.01 <= draw_odd <= 99 and 1.01 <= away_odd <= 99):
            continue
        teams = _extract_teams(event.get('candidates') or [], event.get('text') or '')
        if not teams:
            continue
        kickoff_at = _extract_kickoff(event.get('text') or '', default_kickoff)
        out.append({
            'home': teams[0],
            'away': teams[1],
            'kickoff_at': kickoff_at,
            'home_odd': float(home_odd),
            'draw_odd': float(draw_odd),
            'away_odd': float(away_odd),
        })
    return out

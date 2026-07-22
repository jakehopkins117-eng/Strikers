"""Bullpen workload and availability intelligence for Strikers v3.3."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from typing import Any

import requests

MLB_API = "https://statsapi.mlb.com/api/v1"


@dataclass
class RelieverUsage:
    player_id: int
    name: str
    pitches: int = 0
    appearances: int = 0
    used_yesterday: bool = False
    used_back_to_back: bool = False
    status: str = "Available"


@dataclass
class BullpenData:
    team_id: int
    team_name: str
    availability_score: float = 75.0
    fatigue_level: str = "Unknown"
    games_analyzed: int = 0
    total_pitches_3d: int = 0
    relievers_used_3d: int = 0
    overworked_relievers: int = 0
    unavailable_relievers: int = 0
    season_era: float | None = None
    season_whip: float | None = None
    relievers: list[RelieverUsage] = field(default_factory=list)
    available: bool = False
    note: str = "Bullpen workload data unavailable."

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _json(url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    response = requests.get(url, params=params, timeout=15)
    response.raise_for_status()
    payload = response.json()
    return payload if isinstance(payload, dict) else {}


def _safe_int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _season_reliever_stats(team_id: int, season: int) -> tuple[float | None, float | None]:
    """Request MLB's relief-pitching split. Failure is intentionally non-fatal."""
    try:
        payload = _json(
            f"{MLB_API}/stats",
            {
                "stats": "season",
                "group": "pitching",
                "teamId": team_id,
                "season": season,
                "sitCodes": "rp",
            },
        )
        splits = (payload.get("stats") or [{}])[0].get("splits", [])
        if not splits:
            return None, None
        stat = splits[0].get("stat", {})
        return _safe_float(stat.get("era")), _safe_float(stat.get("whip"))
    except (requests.RequestException, IndexError, TypeError):
        return None, None


def get_bullpen_intelligence(team_id: int, team_name: str, as_of: date | None = None) -> BullpenData:
    """Estimate bullpen availability from the club's previous three calendar days."""
    today = as_of or date.today()
    start = today - timedelta(days=3)
    result = BullpenData(team_id=team_id, team_name=team_name)

    try:
        schedule = _json(
            f"{MLB_API}/schedule",
            {
                "sportId": 1,
                "teamId": team_id,
                "startDate": start.isoformat(),
                "endDate": (today - timedelta(days=1)).isoformat(),
                "gameType": "R",
            },
        )

        usage: dict[int, RelieverUsage] = {}
        used_by_day: dict[str, set[int]] = {}

        games: list[dict[str, Any]] = []
        for group in schedule.get("dates", []):
            games.extend(group.get("games", []))

        for game in games:
            game_pk = game.get("gamePk")
            game_day = str(game.get("officialDate") or "")
            if not game_pk:
                continue
            try:
                box = _json(f"{MLB_API}/game/{game_pk}/boxscore")
            except requests.RequestException:
                continue

            side = None
            teams = game.get("teams", {})
            if teams.get("away", {}).get("team", {}).get("id") == team_id:
                side = "away"
            elif teams.get("home", {}).get("team", {}).get("id") == team_id:
                side = "home"
            if side is None:
                continue

            team_box = box.get("teams", {}).get(side, {})
            pitchers = team_box.get("pitchers", [])
            if not pitchers:
                continue

            # The first listed pitcher is normally the starter. Every later pitcher is relief usage.
            for player_id in pitchers[1:]:
                person = team_box.get("players", {}).get(f"ID{player_id}", {})
                stats = person.get("stats", {}).get("pitching", {})
                pitches = _safe_int(stats.get("numberOfPitches"))
                name = person.get("person", {}).get("fullName", f"Pitcher {player_id}")
                entry = usage.setdefault(player_id, RelieverUsage(player_id=player_id, name=name))
                entry.pitches += pitches
                entry.appearances += 1
                used_by_day.setdefault(game_day, set()).add(player_id)

        yesterday = (today - timedelta(days=1)).isoformat()
        two_days_ago = (today - timedelta(days=2)).isoformat()
        for player_id, entry in usage.items():
            entry.used_yesterday = player_id in used_by_day.get(yesterday, set())
            entry.used_back_to_back = entry.used_yesterday and player_id in used_by_day.get(two_days_ago, set())
            if entry.pitches >= 55 or (entry.used_back_to_back and entry.pitches >= 30):
                entry.status = "Likely unavailable"
            elif entry.pitches >= 35 or entry.used_back_to_back:
                entry.status = "Limited"
            elif entry.used_yesterday:
                entry.status = "Monitor"

        relievers = sorted(usage.values(), key=lambda item: item.pitches, reverse=True)
        unavailable = sum(1 for item in relievers if item.status == "Likely unavailable")
        overworked = sum(1 for item in relievers if item.status in {"Likely unavailable", "Limited"})
        total_pitches = sum(item.pitches for item in relievers)

        penalty = min(total_pitches * 0.28, 35.0) + unavailable * 12.0 + max(0, overworked - unavailable) * 6.0
        score = max(20.0, min(100.0, 100.0 - penalty))
        if score >= 82:
            level = "Fresh"
        elif score >= 65:
            level = "Manageable"
        elif score >= 45:
            level = "Taxed"
        else:
            level = "Critical"

        era, whip = _season_reliever_stats(team_id, today.year)
        result.availability_score = round(score, 1)
        result.fatigue_level = level
        result.games_analyzed = len(games)
        result.total_pitches_3d = total_pitches
        result.relievers_used_3d = len(relievers)
        result.overworked_relievers = overworked
        result.unavailable_relievers = unavailable
        result.season_era = era
        result.season_whip = whip
        result.relievers = relievers[:8]
        result.available = True
        result.note = f"Based on relief appearances during the previous 3 calendar days ({len(games)} games)."
        return result
    except requests.RequestException as error:
        result.note = f"MLB bullpen data request failed: {error}"
        return result

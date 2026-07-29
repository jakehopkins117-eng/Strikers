"""Statcast prediction intelligence for Strikers Sprint 16.3.

The service reads a local, versioned player-metrics cache from
``data/statcast_players.json``. It intentionally does not scrape Baseball
Savant during a prediction request. This keeps predictions fast and prevents a
third-party outage from breaking the site.

When sufficient current lineup or probable-starter data is available, the service
applies a deliberately small and capped probability adjustment. Missing data
continues to fail soft and leaves the existing prediction unchanged.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "statcast_players.json"

HITTER_FIELDS = ("xwoba", "xba", "xslg", "barrel_pct", "hard_hit_pct", "avg_exit_velocity")
PITCHER_FIELDS = ("xera", "xwoba_allowed", "barrel_pct_allowed", "hard_hit_pct_allowed", "avg_exit_velocity_allowed")


def _float(value: Any) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _load_cache() -> dict[str, Any]:
    if not DATA_PATH.exists():
        return {"version": "16.3", "updated_at": None, "players": {}}
    try:
        payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("root must be an object")
        payload.setdefault("players", {})
        return payload
    except (OSError, json.JSONDecodeError, ValueError):
        return {"version": "16.3", "updated_at": None, "players": {}, "invalid": True}


def statcast_status() -> dict[str, Any]:
    cache = _load_cache()
    players = cache.get("players") or {}
    hitter_rows = sum(1 for row in players.values() if isinstance(row, dict) and row.get("hitting"))
    pitcher_rows = sum(1 for row in players.values() if isinstance(row, dict) and row.get("pitching"))
    return {
        "available": bool(players),
        "status": "Ready" if players else "Waiting for data import",
        "version": cache.get("version", "16.2"),
        "updated_at": cache.get("updated_at"),
        "player_count": len(players),
        "hitter_rows": hitter_rows,
        "pitcher_rows": pitcher_rows,
        "data_path": str(DATA_PATH),
        "message": (
            "Statcast cache is loaded and available to the feature layer."
            if players
            else "No Statcast cache is installed yet. Existing predictions remain unchanged."
        ),
    }


def _mean(rows: list[dict[str, Any]], field: str) -> float | None:
    values = [_float(row.get(field)) for row in rows]
    clean = [value for value in values if value is not None]
    return round(sum(clean) / len(clean), 4) if clean else None


def _lineup_side(lineup_side: dict[str, Any], players: dict[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    matched_players: list[dict[str, Any]] = []
    for batter in lineup_side.get("batting_order") or []:
        player_id = batter.get("player_id")
        cached = players.get(str(player_id), {}) if player_id else {}
        hitting = cached.get("hitting") if isinstance(cached, dict) else None
        if isinstance(hitting, dict):
            rows.append(hitting)
            matched_players.append({
                "player_id": player_id,
                "name": batter.get("name"),
                **{field: _float(hitting.get(field)) for field in HITTER_FIELDS},
            })

    completeness = round(len(rows) / 9, 3)
    metrics = {field: _mean(rows, field) for field in HITTER_FIELDS}
    return {
        "available": bool(rows),
        "matched_hitters": len(rows),
        "lineup_completeness": completeness,
        "metrics": metrics,
        "players": matched_players,
    }


def _pitcher_side(pitcher: dict[str, Any], players: dict[str, Any]) -> dict[str, Any]:
    player_id = pitcher.get("id") or pitcher.get("player_id")
    cached = players.get(str(player_id), {}) if player_id else {}
    pitching = cached.get("pitching") if isinstance(cached, dict) else None
    metrics = {
        field: _float((pitching or {}).get(field))
        for field in PITCHER_FIELDS
    }
    return {
        "available": bool(pitching),
        "player_id": player_id,
        "name": pitcher.get("name"),
        "metrics": metrics,
    }


def build_statcast_intelligence(payload: dict[str, Any]) -> dict[str, Any]:
    cache = _load_cache()
    players = cache.get("players") or {}
    lineup = payload.get("lineup_intelligence") or {}

    away_lineup = _lineup_side(lineup.get("away") or {}, players)
    home_lineup = _lineup_side(lineup.get("home") or {}, players)
    away_pitcher = _pitcher_side(payload.get("away_pitcher") or {}, players)
    home_pitcher = _pitcher_side(payload.get("home_pitcher") or {}, players)

    available_sections = sum([
        away_lineup["available"], home_lineup["available"],
        away_pitcher["available"], home_pitcher["available"],
    ])
    return {
        "version": "16.3",
        "available": available_sections > 0,
        "updated_at": cache.get("updated_at"),
        "data_quality_score": round((available_sections / 4) * 100, 1),
        "away": {"lineup": away_lineup, "starter": away_pitcher},
        "home": {"lineup": home_lineup, "starter": home_pitcher},
        "prediction_adjustment": 0.0,
        "mode": "active-conservative",
        "note": (
            "Statcast is available for a conservative, quality-weighted prediction adjustment."
            if available_sections
            else "No Statcast player cache was found, so the current prediction engine was left unchanged."
        ),
    }


def write_empty_cache() -> None:
    """Create a documented empty cache without overwriting existing data."""
    if DATA_PATH.exists():
        return
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(json.dumps({
        "version": "16.3",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "players": {},
    }, indent=2), encoding="utf-8")



def _metric(metrics: dict[str, Any], field: str) -> float | None:
    value = metrics.get(field)
    return _float(value)


def _confidence_from_probability(probability: float) -> tuple[str, str]:
    confidence = "High" if probability >= 65 else "Moderate" if probability >= 57 else "Low"
    stars = "★★★★★" if probability >= 70 else "★★★★☆" if probability >= 63 else "★★★☆☆" if probability >= 56 else "★★☆☆☆"
    return confidence, stars


def apply_statcast_adjustment(
    prediction: dict[str, Any],
    matchup: dict[str, str],
    intelligence: dict[str, Any],
) -> dict[str, Any]:
    """Apply a conservative home-minus-away Statcast edge.

    The adjustment is capped at three probability points and is reduced when
    lineup coverage is incomplete. Starter metrics can still contribute when
    official batting orders have not yet been posted.
    """
    if not intelligence.get("available"):
        return {
            "applied": False,
            "points": 0.0,
            "status": "Unavailable",
            "data_quality_score": intelligence.get("data_quality_score", 0.0),
            "components": {},
        }

    away = intelligence.get("away") or {}
    home = intelligence.get("home") or {}
    away_lineup = (away.get("lineup") or {})
    home_lineup = (home.get("lineup") or {})
    away_starter = (away.get("starter") or {})
    home_starter = (home.get("starter") or {})
    away_hit = away_lineup.get("metrics") or {}
    home_hit = home_lineup.get("metrics") or {}
    away_pitch = away_starter.get("metrics") or {}
    home_pitch = home_starter.get("metrics") or {}

    components: dict[str, float] = {}

    # Positive values favor the home team. Offensive metrics are modestly
    # scaled because lineup averages are season-level rather than matchup-only.
    pairs = (
        ("xwoba", 22.0, 1.15),
        ("xslg", 10.0, 0.80),
        ("barrel_pct", 0.08, 0.65),
        ("hard_hit_pct", 0.15, 0.45),
    )
    lineup_completeness = min(
        float(away_lineup.get("lineup_completeness") or 0.0),
        float(home_lineup.get("lineup_completeness") or 0.0),
    )
    for field, scale, cap in pairs:
        av = _metric(away_hit, field)
        hv = _metric(home_hit, field)
        if av is not None and hv is not None:
            components[f"lineup_{field}"] = max(-cap, min(cap, (hv - av) * scale)) * lineup_completeness

    # Lower xERA/contact allowed is better, so away minus home favors home.
    pitcher_pairs = (
        ("xera", 0.45, 1.25),
        ("xwoba_allowed", 18.0, 0.85),
        ("barrel_pct_allowed", 0.08, 0.50),
        ("hard_hit_pct_allowed", 0.10, 0.35),
    )
    for field, scale, cap in pitcher_pairs:
        av = _metric(away_pitch, field)
        hv = _metric(home_pitch, field)
        if av is not None and hv is not None:
            components[f"starter_{field}"] = max(-cap, min(cap, (av - hv) * scale))

    if not components:
        return {
            "applied": False,
            "points": 0.0,
            "status": "Insufficient matched metrics",
            "data_quality_score": intelligence.get("data_quality_score", 0.0),
            "components": {},
        }

    raw_points = sum(components.values())
    data_quality = float(intelligence.get("data_quality_score") or 0.0) / 100.0
    reliability = max(0.35, min(1.0, data_quality))
    points = max(-3.0, min(3.0, raw_points * reliability))

    # Ignore tiny edges so noise does not alter a pick.
    if abs(points) < 0.15:
        return {
            "applied": False,
            "points": 0.0,
            "raw_points": round(raw_points, 3),
            "status": "Neutral",
            "data_quality_score": intelligence.get("data_quality_score", 0.0),
            "components": {key: round(value, 3) for key, value in components.items()},
        }

    away_probability = float(prediction.get("away_probability", 50.0)) - points
    away_probability = max(20.0, min(80.0, away_probability))
    home_probability = 100.0 - away_probability
    prediction["away_probability"] = round(away_probability, 2)
    prediction["home_probability"] = round(home_probability, 2)
    prediction["winner"] = matchup["away"] if away_probability >= home_probability else matchup["home"]
    win_probability = max(away_probability, home_probability)
    prediction["confidence"], prediction["confidence_stars"] = _confidence_from_probability(win_probability)

    favored = matchup["home"] if points > 0 else matchup["away"]
    reasons = list(prediction.get("reasons", []))
    reasons.append(f"Statcast quality edge: {favored} ({abs(points):.1f} pts)")
    prediction["reasons"] = list(dict.fromkeys(reasons))[:7]
    intelligence["prediction_adjustment"] = round(points, 2)

    return {
        "applied": True,
        "points": round(points, 2),
        "raw_points": round(raw_points, 3),
        "favored_team": favored,
        "status": "Active",
        "maximum_points": 3.0,
        "data_quality_score": intelligence.get("data_quality_score", 0.0),
        "components": {key: round(value, 3) for key, value in components.items()},
    }

"""Lineup and injury intelligence for Strikers v3.4.

Uses public MLB Stats API data and fails soft when a lineup or roster status is
not published.  All probability adjustments are deliberately capped.
"""
from __future__ import annotations

from datetime import date
from typing import Any
import requests

BASE = "https://statsapi.mlb.com/api/v1"
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Strikers/3.4"})


def _get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        response = SESSION.get(f"{BASE}{path}", params=params or {}, timeout=12)
        response.raise_for_status()
        return response.json()
    except Exception:
        return {}


def _find_game_pk(away_id: int, home_id: int, official_date: str | None = None) -> int | None:
    payload = _get("/schedule", {"sportId": 1, "date": official_date or date.today().isoformat()})
    for block in payload.get("dates", []):
        for game in block.get("games", []):
            teams = game.get("teams", {})
            if teams.get("away", {}).get("team", {}).get("id") == away_id and teams.get("home", {}).get("team", {}).get("id") == home_id:
                return game.get("gamePk")
    return None


def _player_season_ops(player_id: int, season: int) -> float:
    payload = _get(f"/people/{player_id}/stats", {"stats": "season", "group": "hitting", "season": season})
    try:
        return float(payload["stats"][0]["splits"][0]["stat"].get("ops") or 0.0)
    except (KeyError, IndexError, TypeError, ValueError):
        return 0.0


def _lineup_side(boxscore: dict[str, Any], side: str, season: int) -> dict[str, Any]:
    team_data = boxscore.get("teams", {}).get(side, {})
    players = team_data.get("players", {})
    batting_order = team_data.get("battingOrder", []) or []
    lineup: list[dict[str, Any]] = []
    ops_values: list[float] = []
    for raw_id in batting_order[:9]:
        player = players.get(f"ID{raw_id}", {})
        person = player.get("person", {})
        stats = player.get("seasonStats", {}).get("batting", {})
        try:
            ops = float(stats.get("ops") or 0.0)
        except (TypeError, ValueError):
            ops = 0.0
        if ops <= 0 and person.get("id"):
            ops = _player_season_ops(int(person["id"]), season)
        if ops > 0:
            ops_values.append(ops)
        lineup.append({
            "player_id": person.get("id", raw_id),
            "name": person.get("fullName", "Unknown Player"),
            "position": player.get("position", {}).get("abbreviation", ""),
            "ops": round(ops, 3) if ops else None,
        })
    confirmed = len(lineup) >= 9
    average_ops = sum(ops_values) / len(ops_values) if ops_values else 0.0
    # .700 OPS maps near 70; clamp to avoid false precision.
    strength = max(45.0, min(100.0, average_ops * 100)) if average_ops else 65.0
    return {
        "status": "Confirmed" if confirmed else "Projected / unavailable",
        "confirmed": confirmed,
        "strength_score": round(strength, 1),
        "average_ops": round(average_ops, 3) if average_ops else None,
        "batting_order": lineup,
        "note": "Official MLB batting order." if confirmed else "MLB has not published a complete batting order yet.",
    }


def get_lineup_intelligence(away_id: int, home_id: int, game_pk: int | None = None, official_date: str | None = None) -> dict[str, Any]:
    resolved_pk = game_pk or _find_game_pk(away_id, home_id, official_date)
    if not resolved_pk:
        empty = {"status": "Projected / unavailable", "confirmed": False, "strength_score": 65.0, "average_ops": None, "batting_order": [], "note": "No matching MLB game was found."}
        return {"game_pk": None, "away": empty, "home": dict(empty), "available": False}
    feed = _get(f".1/game/{resolved_pk}/feed/live".replace(".1/", "/v1.1/"))
    # BASE is /api/v1; v1.1 requires absolute replacement fallback.
    if not feed:
        try:
            response = SESSION.get(f"https://statsapi.mlb.com/api/v1.1/game/{resolved_pk}/feed/live", timeout=12)
            response.raise_for_status(); feed = response.json()
        except Exception:
            feed = {}
    season = int((official_date or date.today().isoformat())[:4])
    boxscore = feed.get("liveData", {}).get("boxscore", {})
    away = _lineup_side(boxscore, "away", season)
    home = _lineup_side(boxscore, "home", season)
    return {"game_pk": resolved_pk, "away": away, "home": home, "available": away["confirmed"] or home["confirmed"]}


def _injured_roster(team_id: int) -> list[dict[str, Any]]:
    # MLB supports rosterType=injuredList. Some days it returns an empty list;
    # that is treated as no published IL entries rather than an error.
    payload = _get(f"/teams/{team_id}/roster", {"rosterType": "injuredList", "hydrate": "person"})
    items: list[dict[str, Any]] = []
    for entry in payload.get("roster", []):
        person = entry.get("person", {})
        status = entry.get("status", {})
        position = entry.get("position", {}).get("abbreviation", "")
        status_text = status.get("description") or status.get("code") or "Injured List"
        impact = "High" if position in {"P", "SP", "RP", "C", "SS", "CF"} else "Medium"
        items.append({
            "player_id": person.get("id"),
            "name": person.get("fullName", "Unknown Player"),
            "position": position,
            "status": status_text,
            "impact": impact,
        })
    return items


def get_injury_intelligence(away_id: int, home_id: int) -> dict[str, Any]:
    away = _injured_roster(away_id)
    home = _injured_roster(home_id)
    def score(players: list[dict[str, Any]]) -> float:
        # Small, capped team-level penalty; lineup absences provide the game-specific signal.
        raw = sum(0.45 if p["impact"] == "High" else 0.25 for p in players)
        return round(min(3.0, raw), 2)
    return {
        "away": {"players": away, "count": len(away), "penalty_points": score(away)},
        "home": {"players": home, "count": len(home), "penalty_points": score(home)},
        "available": True,
        "note": "Official MLB injured-list roster entries. Day-to-day issues and late scratches may not appear here.",
    }


def apply_lineup_injury_adjustment(prediction: dict[str, Any], matchup: dict[str, str], lineup: dict[str, Any], injuries: dict[str, Any]) -> dict[str, Any]:
    away = float(prediction["away_probability"])
    # Lineup differential: at most 3 percentage points.
    lineup_delta = (float(lineup["away"]["strength_score"]) - float(lineup["home"]["strength_score"])) * 0.10
    if not (lineup["away"]["confirmed"] and lineup["home"]["confirmed"]):
        lineup_delta *= 0.35
    lineup_delta = max(-3.0, min(3.0, lineup_delta))
    injury_delta = float(injuries["home"]["penalty_points"]) - float(injuries["away"]["penalty_points"])
    total_delta = max(-4.0, min(4.0, lineup_delta + injury_delta))
    away = max(20.0, min(80.0, away + total_delta))
    home = 100.0 - away
    prediction["away_probability"] = round(away, 2)
    prediction["home_probability"] = round(home, 2)
    prediction["winner"] = matchup["away"] if away >= home else matchup["home"]
    win_prob = max(away, home)
    prediction["confidence"] = "High" if win_prob >= 65 else "Moderate" if win_prob >= 57 else "Low"
    prediction["confidence_stars"] = "★★★★★" if win_prob >= 70 else "★★★★☆" if win_prob >= 63 else "★★★☆☆" if win_prob >= 56 else "★★☆☆☆"
    reasons = list(prediction.get("reasons", []))
    if abs(lineup_delta) >= 0.5:
        reasons.append(f"Confirmed lineup edge: {matchup['away'] if lineup_delta > 0 else matchup['home']}")
    if abs(injury_delta) >= 0.5:
        reasons.append(f"Injury availability edge: {matchup['away'] if injury_delta > 0 else matchup['home']}")
    prediction["reasons"] = list(dict.fromkeys(reasons))[:6]
    return {"lineup_adjustment": round(lineup_delta, 2), "injury_adjustment": round(injury_delta, 2), "total_adjustment": round(total_delta, 2)}


def build_game_analyst(payload: dict[str, Any], adjustments: dict[str, Any]) -> dict[str, Any]:
    pred = payload["prediction"]; matchup = payload["matchup"]
    winner = pred["winner"]; loser = matchup["home"] if winner == matchup["away"] else matchup["away"]
    reasons = list(pred.get("reasons", []))[:5]
    lineup = payload["lineup_intelligence"]; injuries = payload["injury_intelligence"]
    risks: list[str] = []
    if not (lineup["away"]["confirmed"] and lineup["home"]["confirmed"]):
        risks.append("One or both official batting orders are not confirmed, so the pick may move before first pitch.")
    winner_side = "away" if winner == matchup["away"] else "home"
    if injuries[winner_side]["count"]:
        risks.append(f"{winner} has {injuries[winner_side]['count']} player(s) listed on the official injured roster.")
    if not risks:
        risks.append(f"The model edge over {loser} is not large enough to remove normal baseball variance.")
    probability = max(float(pred["away_probability"]), float(pred["home_probability"]))
    return {
        "title": "Strikers AI Game Analyst",
        "pick": winner,
        "win_probability": round(probability, 1),
        "verdict": f"{pred['confidence']}-confidence lean to {winner}.",
        "summary": f"Strikers favors {winner} at {probability:.1f}% after combining team form, starting pitching, bullpen availability, the current lineup signal, and official injured-list availability.",
        "key_reasons": reasons,
        "biggest_risks": risks,
        "lineup_status": f"Away: {lineup['away']['status']} · Home: {lineup['home']['status']}",
        "model_adjustment": adjustments,
        "disclaimer": "Model-generated analysis, not financial advice. MLB lineup and injury feeds can change close to first pitch.",
    }

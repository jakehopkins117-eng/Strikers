"""Strikers FastAPI web bridge — Sprint 6.

Features:
- Live MLB schedule
- MLB teams and logos
- Matchup predictions through Prediction Engine 4.0
- Automatic Best Bets
- Power Rankings
- Persistent Prediction History

The history file is created automatically at:
data/prediction_history.json
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date as date_type, datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from services.prediction import PredictionEngine
from services.performance import build_performance, grade_predictions
from services.weather import weather_for_game
from services.model_intelligence import build_model_intelligence, model_lab_payload
from services.betting_intelligence import evaluate_moneyline
from services.prediction_database import (
    clear_predictions as clear_sqlite_predictions,
    initialize_database,
    import_legacy_history,
    list_predictions as list_sqlite_predictions,
    save_prediction as save_sqlite_prediction,
    summary as database_summary,
)
from services.ml_foundation import model_status, second_opinion


app = FastAPI(
    title="Strikers API",
    version="10.12.0",
    description="Web API for the Strikers MLB prediction platform.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

MLB_STATS_API = "https://statsapi.mlb.com/api/v1"
HISTORY_PATH = Path(__file__).resolve().parent / "data" / "prediction_history.json"
HISTORY_LOCK = Lock()


class PredictionRequest(BaseModel):
    away_team: str = Field(min_length=2, max_length=80)
    home_team: str = Field(min_length=2, max_length=80)
    away_odds: int | None = Field(default=None, ge=-10000, le=10000)
    home_odds: int | None = Field(default=None, ge=-10000, le=10000)


class BettingIntelligenceRequest(BaseModel):
    away_team: str = Field(min_length=2, max_length=80)
    home_team: str = Field(min_length=2, max_length=80)
    away_odds: int = Field(ge=-10000, le=10000)
    home_odds: int = Field(ge=-10000, le=10000)


class PropAnalysisRequest(BaseModel):
    player: str = Field(min_length=2, max_length=100)
    market: str = Field(min_length=2, max_length=80)
    projection: float = Field(ge=0)
    line: float = Field(ge=0)
    over_odds: int = Field(default=-110, ge=-10000, le=10000)
    under_odds: int = Field(default=-110, ge=-10000, le=10000)


def _get_json(url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        response = requests.get(url, params=params, timeout=20)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as error:
        raise HTTPException(
            status_code=502,
            detail=f"MLB data request failed: {error}",
        ) from error


def _logo_url(team_id: int | None) -> str | None:
    if not team_id:
        return None
    return f"https://www.mlbstatic.com/team-logos/{team_id}.svg"


def _team_payload(team: dict[str, Any]) -> dict[str, Any]:
    team_id = team.get("id")
    return {
        "id": team_id,
        "name": team.get("name", "Unknown Team"),
        "logo": _logo_url(team_id),
    }


def _probable_pitcher(game_team: dict[str, Any]) -> dict[str, Any] | None:
    pitcher = game_team.get("probablePitcher")
    if not pitcher:
        return None
    return {
        "id": pitcher.get("id"),
        "name": pitcher.get("fullName", "TBD"),
    }


def _schedule_game_payload(game: dict[str, Any]) -> dict[str, Any]:
    teams = game.get("teams", {})
    away = teams.get("away", {})
    home = teams.get("home", {})
    status = game.get("status", {})

    return {
        "game_pk": game.get("gamePk"),
        "game_date": game.get("gameDate"),
        "official_date": game.get("officialDate"),
        "status": {
            "abstract": status.get("abstractGameState", "Preview"),
            "detailed": status.get("detailedState", "Scheduled"),
        },
        "venue": game.get("venue", {}).get("name"),
        "away": {
            **_team_payload(away.get("team", {})),
            "probable_pitcher": _probable_pitcher(away),
            "score": away.get("score"),
        },
        "home": {
            **_team_payload(home.get("team", {})),
            "probable_pitcher": _probable_pitcher(home),
            "score": home.get("score"),
        },
    }


def _team_stats_payload(team_data: Any) -> dict[str, Any]:
    if team_data is None:
        return {}

    fields = [
        "team_id",
        "name",
        "win_pct",
        "location_win_pct",
        "ops",
        "runs_per_game",
        "era",
        "whip",
        "recent_games",
        "recent_wins",
        "recent_losses",
        "recent_win_pct",
        "recent_runs_per_game",
        "recent_runs_allowed_per_game",
        "recent_run_differential_per_game",
    ]

    result: dict[str, Any] = {}
    for field in fields:
        value = getattr(team_data, field, None)
        result["id" if field == "team_id" else field] = value

    result["logo"] = _logo_url(result.get("id"))
    return result


def _pitcher_payload(pitcher: Any) -> dict[str, Any]:
    if pitcher is None:
        return {
            "id": None,
            "name": "TBD",
            "available": False,
            "era": None,
            "whip": None,
            "innings": None,
            "strikeouts": None,
            "walks": None,
            "opponent_average": None,
        }

    available = bool(getattr(pitcher, "available", False))
    return {
        "id": getattr(pitcher, "player_id", None),
        "name": getattr(pitcher, "name", "TBD"),
        "available": available,
        "era": getattr(pitcher, "era", None) if available else None,
        "whip": getattr(pitcher, "whip", None) if available else None,
        "innings": getattr(pitcher, "innings", None) if available else None,
        "strikeouts": getattr(pitcher, "strikeouts", None) if available else None,
        "walks": getattr(pitcher, "walks", None) if available else None,
        "opponent_average": (
            getattr(pitcher, "opponent_average", None) if available else None
        ),
    }


def _read_history() -> list[dict[str, Any]]:
    with HISTORY_LOCK:
        if not HISTORY_PATH.exists():
            return []

        try:
            payload = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []

        return payload if isinstance(payload, list) else []


def _write_history(history: list[dict[str, Any]]) -> None:
    with HISTORY_LOCK:
        HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        temp_path = HISTORY_PATH.with_suffix(".tmp")
        temp_path.write_text(
            json.dumps(history, indent=2),
            encoding="utf-8",
        )
        temp_path.replace(HISTORY_PATH)


def _save_prediction(payload: dict[str, Any]) -> dict[str, Any]:
    prediction = payload["prediction"]
    history_item = {
        "id": str(uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "away_team": payload["matchup"]["away"],
        "home_team": payload["matchup"]["home"],
        "winner": prediction["winner"],
        "away_probability": float(prediction["away_probability"]),
        "home_probability": float(prediction["home_probability"]),
        "confidence": prediction["confidence"],
        "confidence_stars": prediction["confidence_stars"],
        "projected_score": {
            "away": prediction.get("away_score"),
            "home": prediction.get("home_score"),
        },
        "reasons": prediction.get("reasons", []),
        "away_logo": payload["away_team"].get("logo"),
        "home_logo": payload["home_team"].get("logo"),
    }

    history = _read_history()
    history.insert(0, history_item)
    _write_history(history[:250])
    return history_item



def _metric_value(source: dict[str, Any], key: str) -> float | None:
    value = source.get(key)
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _build_game_intelligence(payload: dict[str, Any]) -> dict[str, Any]:
    prediction = payload["prediction"]
    away = payload["away_team"]
    home = payload["home_team"]
    away_pitcher = payload["away_pitcher"]
    home_pitcher = payload["home_pitcher"]

    away_name = payload["matchup"]["away"]
    home_name = payload["matchup"]["home"]
    winner = str(prediction["winner"])
    loser = home_name if winner == away_name else away_name
    winner_data = away if winner == away_name else home
    loser_data = home if winner == away_name else away
    winner_pitcher = away_pitcher if winner == away_name else home_pitcher
    loser_pitcher = home_pitcher if winner == away_name else away_pitcher

    away_probability = float(prediction["away_probability"])
    home_probability = float(prediction["home_probability"])
    confidence = max(away_probability, home_probability)
    edge = abs(away_probability - home_probability)

    advantages: list[str] = []
    risks: list[str] = []
    watch_items: list[str] = []

    winner_win_pct = _metric_value(winner_data, "win_pct")
    loser_win_pct = _metric_value(loser_data, "win_pct")
    if winner_win_pct is not None and loser_win_pct is not None:
        difference = winner_win_pct - loser_win_pct
        if difference >= 0.03:
            advantages.append(
                f"{winner} owns a {difference * 100:.1f}-point season win-rate advantage."
            )
        elif difference <= -0.03:
            risks.append(
                f"{winner} has the weaker season record, so the pick depends more on matchup-specific edges."
            )

    winner_recent = _metric_value(winner_data, "recent_win_pct")
    loser_recent = _metric_value(loser_data, "recent_win_pct")
    if winner_recent is not None and loser_recent is not None:
        difference = winner_recent - loser_recent
        if difference >= 0.08:
            advantages.append(
                f"Recent form favors {winner} by {difference * 100:.1f} percentage points."
            )
        elif difference <= -0.08:
            risks.append(
                f"{loser} enters with better recent form, creating upset risk."
            )

    winner_ops = _metric_value(winner_data, "ops")
    loser_ops = _metric_value(loser_data, "ops")
    if winner_ops is not None and loser_ops is not None:
        difference = winner_ops - loser_ops
        if difference >= 0.020:
            advantages.append(
                f"{winner} carries the stronger offense with a {difference:.3f} OPS edge."
            )
        elif difference <= -0.020:
            risks.append(
                f"{winner} trails in OPS by {abs(difference):.3f}, so run production is not guaranteed."
            )

    winner_rpg = _metric_value(winner_data, "runs_per_game")
    loser_rpg = _metric_value(loser_data, "runs_per_game")
    if winner_rpg is not None and loser_rpg is not None:
        difference = winner_rpg - loser_rpg
        if difference >= 0.30:
            advantages.append(
                f"{winner} scores {difference:.2f} more runs per game."
            )

    winner_era = _metric_value(winner_data, "era")
    loser_era = _metric_value(loser_data, "era")
    if winner_era is not None and loser_era is not None:
        difference = loser_era - winner_era
        if difference >= 0.25:
            advantages.append(
                f"Team pitching favors {winner} by {difference:.2f} ERA."
            )
        elif difference <= -0.25:
            risks.append(
                f"{loser} owns the stronger staff ERA by {abs(difference):.2f}."
            )

    winner_recent_rd = _metric_value(
        winner_data,
        "recent_run_differential_per_game",
    )
    loser_recent_rd = _metric_value(
        loser_data,
        "recent_run_differential_per_game",
    )
    if winner_recent_rd is not None and loser_recent_rd is not None:
        difference = winner_recent_rd - loser_recent_rd
        if difference >= 0.40:
            advantages.append(
                f"Recent run differential gives {winner} a {difference:+.2f} runs-per-game edge."
            )
        elif difference <= -0.40:
            risks.append(
                f"Recent run differential actually favors {loser} by {abs(difference):.2f} runs per game."
            )

    winner_pitcher_era = _metric_value(winner_pitcher, "era")
    loser_pitcher_era = _metric_value(loser_pitcher, "era")
    if winner_pitcher_era is not None and loser_pitcher_era is not None:
        difference = loser_pitcher_era - winner_pitcher_era
        if difference >= 0.35:
            advantages.append(
                f"The projected starter matchup favors {winner} by {difference:.2f} ERA."
            )
        elif difference <= -0.35:
            risks.append(
                f"The opposing starter has the better ERA by {abs(difference):.2f}."
            )
    else:
        watch_items.append(
            "Probable-pitcher data is incomplete; confirm the starters before relying on the pick."
        )

    if edge < 5:
        risks.append(
            "The model sees a near coin flip, so small lineup or bullpen changes could reverse the pick."
        )
    elif edge >= 15:
        advantages.append(
            f"The model creates a clear {edge:.1f}-point probability gap."
        )

    watch_items.extend([
        "Check confirmed lineups and late scratches before first pitch.",
        "Monitor bullpen availability, especially after extra-inning or high-pitch-count games.",
    ])

    if confidence >= 70:
        grade = "Strong"
        headline = f"{winner} has the clearest overall matchup edge."
    elif confidence >= 62:
        grade = "Playable"
        headline = f"{winner} has a meaningful but not overwhelming edge."
    elif confidence >= 56:
        grade = "Lean"
        headline = f"{winner} is the model lean in a competitive matchup."
    else:
        grade = "Pass"
        headline = "The matchup is too close for a high-conviction position."

    projected_away = prediction.get("away_score")
    projected_home = prediction.get("home_score")
    score_text = ""
    if projected_away is not None and projected_home is not None:
        score_text = (
            f"The projected score is {away_name} {projected_away} "
            f"to {home_name} {projected_home}."
        )

    summary_parts = [
        headline,
        advantages[0] if advantages else (
            f"The model probability is the primary reason for the {winner} lean."
        ),
    ]
    if score_text:
        summary_parts.append(score_text)

    return {
        "headline": headline,
        "summary": " ".join(summary_parts),
        "grade": grade,
        "edge_points": round(edge, 1),
        "advantages": advantages[:5],
        "risks": risks[:4],
        "watch_items": watch_items[:4],
        "recommended_action": (
            "Consider"
            if grade in {"Strong", "Playable"}
            else "Lean only"
            if grade == "Lean"
            else "Pass"
        ),
        "disclaimer": (
            "Model analysis is informational and cannot account for every "
            "late lineup, injury, weather, or market change."
        ),
    }


def _run_prediction(
    away_team: str,
    home_team: str,
    *,
    save_history: bool,
    away_odds: int | None = None,
    home_odds: int | None = None,
) -> dict[str, Any]:
    if away_team == home_team:
        raise HTTPException(
            status_code=400,
            detail="Please choose two different teams.",
        )

    engine = PredictionEngine()

    try:
        result = engine.predict_silent(away_team, home_team)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except (ConnectionError, RuntimeError) as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Prediction failed: {error}",
        ) from error

    prediction = asdict(result)

    payload = {
        "matchup": {
            "away": getattr(engine.away_data, "name", away_team),
            "home": getattr(engine.home_data, "name", home_team),
        },
        "prediction": prediction,
        "away_team": _team_stats_payload(engine.away_data),
        "home_team": _team_stats_payload(engine.home_data),
        "away_pitcher": _pitcher_payload(engine.away_pitcher),
        "home_pitcher": _pitcher_payload(engine.home_pitcher),
    }
    payload["intelligence"] = build_model_intelligence(payload)
    payload["betting_intelligence"] = evaluate_moneyline(
        away_team=payload["matchup"]["away"], home_team=payload["matchup"]["home"],
        away_probability=float(prediction["away_probability"]), home_probability=float(prediction["home_probability"]),
        away_odds=away_odds, home_odds=home_odds,
    )
    payload["ml_second_opinion"] = second_opinion(payload)

    if save_history:
        history_item = _save_prediction(payload)
        payload["history_id"] = save_sqlite_prediction(payload, payload["betting_intelligence"], record_id=history_item["id"], created_at=history_item["created_at"])

    return payload


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default



def _american_to_decimal(odds: int) -> float:
    if odds == 0:
        return 2.0
    return 1 + (100 / abs(odds) if odds < 0 else odds / 100)


def _american_implied(odds: int) -> float:
    if odds == 0:
        return 0.5
    return abs(odds) / (abs(odds) + 100) if odds < 0 else 100 / (odds + 100)


def _fair_american(probability: float) -> int:
    probability = max(0.01, min(0.99, probability))
    return round(-100 * probability / (1 - probability)) if probability >= 0.5 else round(100 * (1 - probability) / probability)


def _normal_over_probability(projection: float, line: float, scale: float) -> float:
    # Smooth, transparent approximation suitable for a first projection model.
    import math
    z = (projection - line) / max(scale, 0.25)
    return max(0.05, min(0.95, 1 / (1 + math.exp(-1.7 * z))))


def _season_value(stats: dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        return float(stats.get(key, default) or default)
    except (TypeError, ValueError):
        return default


def _team_roster_stats(team_id: int, season: int) -> list[dict[str, Any]]:
    payload = _get_json(
        f"{MLB_STATS_API}/teams/{team_id}/roster",
        params={
            "rosterType": "active",
            "hydrate": f"person(stats(group=[hitting,pitching],type=[season],season={season}))",
        },
    )
    players: list[dict[str, Any]] = []
    for entry in payload.get("roster", []):
        person = entry.get("person", {})
        groups: dict[str, dict[str, Any]] = {}
        for block in person.get("stats", []):
            group = block.get("group", {}).get("displayName", "")
            splits = block.get("splits", [])
            if splits:
                groups[group] = splits[0].get("stat", {})
        players.append({
            "id": person.get("id"),
            "name": person.get("fullName", "Unknown Player"),
            "position": entry.get("position", {}).get("abbreviation", ""),
            "hitting": groups.get("hitting", {}),
            "pitching": groups.get("pitching", {}),
        })
    return players


def _confidence_label(probability: float) -> str:
    edge = abs(probability - 0.5)
    if edge >= .20: return "Strong"
    if edge >= .13: return "Playable"
    if edge >= .07: return "Lean"
    return "Pass"


def _prop_card(player: str, player_id: int | None, team: dict[str, Any], opponent: dict[str, Any], market: str, projection: float, default_line: float, scale: float, reasons: list[str]) -> dict[str, Any]:
    over_probability = _normal_over_probability(projection, default_line, scale)
    recommendation = "OVER" if over_probability >= .56 else "UNDER" if over_probability <= .44 else "PASS"
    probability = over_probability if recommendation != "UNDER" else 1-over_probability
    return {
        "id": f"{player_id or player}-{market}".replace(" ", "-").lower(),
        "player_id": player_id,
        "player": player,
        "team": team,
        "opponent": opponent,
        "market": market,
        "projection": round(projection, 2),
        "suggested_line": default_line,
        "over_probability": round(over_probability * 100, 1),
        "under_probability": round((1-over_probability) * 100, 1),
        "recommendation": recommendation,
        "confidence": _confidence_label(probability),
        "fair_over_odds": _fair_american(over_probability),
        "fair_under_odds": _fair_american(1-over_probability),
        "reasons": reasons[:4],
    }


def _build_daily_props(target_date: str, limit: int) -> list[dict[str, Any]]:
    schedule = _get_json(
        f"{MLB_STATS_API}/schedule",
        params={"sportId": 1, "date": target_date, "hydrate": "probablePitcher"},
    )
    games = [g for d in schedule.get("dates", []) for g in d.get("games", [])]
    season = int(target_date[:4])
    props: list[dict[str, Any]] = []
    roster_cache: dict[int, list[dict[str, Any]]] = {}

    for game in games:
        sides = game.get("teams", {})
        for side, other in (("away", "home"), ("home", "away")):
            team = sides.get(side, {}).get("team", {})
            opponent = sides.get(other, {}).get("team", {})
            team_id = team.get("id")
            if not team_id:
                continue
            if team_id not in roster_cache:
                roster_cache[team_id] = _team_roster_stats(team_id, season)
            players = roster_cache[team_id]

            probable = sides.get(side, {}).get("probablePitcher", {})
            probable_id = probable.get("id")
            pitcher = next((p for p in players if p["id"] == probable_id), None)
            if pitcher and pitcher["pitching"]:
                st = pitcher["pitching"]
                games_started = max(_season_value(st, "gamesStarted", 1), 1)
                innings = _season_value(st, "inningsPitched")
                strikeouts = _season_value(st, "strikeOuts")
                walks = _season_value(st, "baseOnBalls")
                earned = _season_value(st, "earnedRuns")
                hits = _season_value(st, "hits")
                k_proj = strikeouts / games_started if games_started else 0
                outs_proj = (innings * 3) / games_started if games_started else 15
                er_proj = earned / games_started if games_started else 2.5
                hit_proj = hits / games_started if games_started else 5.5
                bb_proj = walks / games_started if games_started else 2.0
                team_payload={"id":team_id,"name":team.get("name"),"logo":_logo_url(team_id)}
                opp_payload={"id":opponent.get("id"),"name":opponent.get("name"),"logo":_logo_url(opponent.get("id"))}
                pitcher_name=pitcher["name"]
                props.extend([
                    _prop_card(pitcher_name, probable_id, team_payload, opp_payload, "Pitcher Strikeouts", k_proj, round(k_proj*2)/2, 1.6, [f"Season rate: {k_proj:.1f} strikeouts per start", f"{innings:.1f} innings across {int(games_started)} starts", "Confirm pitch count and lineup before first pitch"]),
                    _prop_card(pitcher_name, probable_id, team_payload, opp_payload, "Pitcher Outs", outs_proj, round(outs_proj*2)/2, 2.5, [f"Season workload projects to {outs_proj:.1f} outs", f"Walk rate: {bb_proj:.1f} per start", "Bullpen usage can affect leash"]),
                    _prop_card(pitcher_name, probable_id, team_payload, opp_payload, "Earned Runs", er_proj, round(er_proj*2)/2, 1.0, [f"Season rate: {er_proj:.2f} earned runs per start", f"Hits allowed: {hit_proj:.1f} per start", "Defense and park conditions add volatility"]),
                ])

            hitters=[]
            for p in players:
                st=p["hitting"]
                pa=_season_value(st,"plateAppearances")
                games_played=_season_value(st,"gamesPlayed")
                if games_played < 5 or pa < 15: continue
                ops=_season_value(st,"ops")
                hitters.append((ops, games_played, p, st))
            hitters.sort(reverse=True, key=lambda x:x[0])
            for _, gp, hitter, st in hitters[:3]:
                hits=_season_value(st,"hits")/gp
                tb=_season_value(st,"totalBases")/gp
                hr=_season_value(st,"homeRuns")/gp
                rbi=_season_value(st,"rbi")/gp
                avg=st.get("avg",".000"); ops=st.get("ops",".000")
                tp={"id":team_id,"name":team.get("name"),"logo":_logo_url(team_id)}
                op={"id":opponent.get("id"),"name":opponent.get("name"),"logo":_logo_url(opponent.get("id"))}
                name=hitter["name"]; pid=hitter["id"]
                props.extend([
                    _prop_card(name,pid,tp,op,"Hits",hits,1.5 if hits>=1.15 else .5,.55,[f"Season average: {hits:.2f} hits/game",f"Batting average: {avg}",f"OPS: {ops}"]),
                    _prop_card(name,pid,tp,op,"Total Bases",tb,1.5,.85,[f"Season average: {tb:.2f} total bases/game",f"OPS: {ops}","Extra-base hits create upside"]),
                    _prop_card(name,pid,tp,op,"Home Runs",hr,.5,.28,[f"Season rate: {hr:.2f} home runs/game",f"OPS: {ops}","Home-run props are high variance"]),
                    _prop_card(name,pid,tp,op,"RBIs",rbi,.5,.55,[f"Season average: {rbi:.2f} RBI/game",f"OPS: {ops}","Lineup position drives opportunity"]),
                ])

    rank={"Strong":0,"Playable":1,"Lean":2,"Pass":3}
    props.sort(key=lambda p:(rank[p["confidence"]], -abs(p["over_probability"]-50)))
    return props[:limit]


@app.get("/")
def root() -> dict[str, str]:
    return {
        "message": "Strikers API is running.",
        "engine": "Prediction Engine 7.5",
        "release": "3.0",
    }


@app.get("/health")
def health() -> dict[str, str]:
    initialize_database()
    import_legacy_history(_read_history())
    return {"status": "online", "engine": "7.5", "release": "3.0"}


@app.get("/teams")
def teams() -> dict[str, list[dict[str, Any]]]:
    data = _get_json(f"{MLB_STATS_API}/teams", {"sportId": 1})
    result = [
        {
            "id": team.get("id"),
            "name": team.get("name"),
            "logo": _logo_url(team.get("id")),
        }
        for team in data.get("teams", [])
        if team.get("active", True)
    ]
    result.sort(key=lambda item: item["name"] or "")
    return {"teams": result}


@app.get("/schedule")
def schedule(
    game_date: str = Query(
        default_factory=lambda: date_type.today().isoformat(),
        alias="date",
    ),
) -> dict[str, Any]:
    data = _get_json(
        f"{MLB_STATS_API}/schedule",
        {
            "sportId": 1,
            "date": game_date,
            "hydrate": "probablePitcher,team,venue",
        },
    )

    games: list[dict[str, Any]] = []
    for date_block in data.get("dates", []):
        games.extend(
            _schedule_game_payload(game)
            for game in date_block.get("games", [])
        )

    return {
        "date": game_date,
        "total_games": len(games),
        "games": games,
    }


@app.post("/predict")
def predict_matchup(request: PredictionRequest) -> dict[str, Any]:
    return _run_prediction(
        request.away_team, request.home_team, save_history=True,
        away_odds=request.away_odds, home_odds=request.home_odds,
    )


@app.post("/betting-intelligence")
def betting_intelligence(request: BettingIntelligenceRequest) -> dict[str, Any]:
    return _run_prediction(
        request.away_team, request.home_team, save_history=False,
        away_odds=request.away_odds, home_odds=request.home_odds,
    )["betting_intelligence"]


@app.get("/ml/status")
def ml_status() -> dict[str, Any]:
    return model_status()


@app.get("/dashboard-summary")
def dashboard_summary() -> dict[str, Any]:
    return {"database": database_summary(), "ml": model_status(), "engine": "7.5", "release": "3.0"}


@app.get("/best-bets")
def best_bets(
    game_date: str = Query(
        default_factory=lambda: date_type.today().isoformat(),
        alias="date",
    ),
    limit: int = Query(default=5, ge=1, le=15),
) -> dict[str, Any]:
    schedule_payload = schedule(game_date)
    ranked: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []

    for game in schedule_payload["games"]:
        away_name = game["away"]["name"]
        home_name = game["home"]["name"]

        try:
            result = _run_prediction(
                away_name,
                home_name,
                save_history=False,
            )
            prediction = result["prediction"]
            away_probability = float(prediction["away_probability"])
            home_probability = float(prediction["home_probability"])
            confidence = max(away_probability, home_probability)

            ranked.append(
                {
                    "game": game,
                    "winner": prediction["winner"],
                    "probability": confidence,
                    "confidence": prediction["confidence"],
                    "confidence_stars": prediction["confidence_stars"],
                    "reasons": prediction.get("reasons", []),
                    "away_probability": away_probability,
                    "home_probability": home_probability,
                }
            )
        except HTTPException as error:
            failures.append(
                {
                    "matchup": f"{away_name} at {home_name}",
                    "reason": str(error.detail),
                }
            )

    ranked.sort(key=lambda item: item["probability"], reverse=True)

    return {
        "date": game_date,
        "bets": ranked[:limit],
        "analyzed": len(ranked),
        "failed": failures,
    }


@app.get("/power-rankings")
def power_rankings(
    season: int = Query(default_factory=lambda: date_type.today().year),
) -> dict[str, Any]:
    standings = _get_json(
        f"{MLB_STATS_API}/standings",
        {
            "leagueId": "103,104",
            "season": season,
            "standingsTypes": "regularSeason",
            "hydrate": "team",
        },
    )

    rankings: list[dict[str, Any]] = []

    for record_group in standings.get("records", []):
        for team_record in record_group.get("teamRecords", []):
            team = team_record.get("team", {})
            wins = int(team_record.get("wins", 0))
            losses = int(team_record.get("losses", 0))
            games_played = max(wins + losses, 1)
            win_pct = _safe_float(team_record.get("winningPercentage"))
            run_diff = int(team_record.get("runDifferential", 0))
            last_ten = team_record.get("records", {}).get("splitRecords", [])

            last_ten_wins = 0
            last_ten_losses = 0
            for split in last_ten:
                if split.get("type") == "lastTen":
                    last_ten_wins = int(split.get("wins", 0))
                    last_ten_losses = int(split.get("losses", 0))
                    break

            recent_games = last_ten_wins + last_ten_losses
            recent_pct = (
                last_ten_wins / recent_games if recent_games else win_pct
            )
            run_diff_per_game = run_diff / games_played

            # Transparent composite score:
            # 65% season record, 20% recent form, 15% run differential.
            normalized_run_diff = max(
                0.0,
                min(1.0, 0.5 + (run_diff_per_game / 4.0)),
            )
            power_score = (
                win_pct * 65.0
                + recent_pct * 20.0
                + normalized_run_diff * 15.0
            )

            rankings.append(
                {
                    "team_id": team.get("id"),
                    "team": team.get("name", "Unknown Team"),
                    "logo": _logo_url(team.get("id")),
                    "wins": wins,
                    "losses": losses,
                    "win_pct": win_pct,
                    "run_differential": run_diff,
                    "last_ten": f"{last_ten_wins}-{last_ten_losses}",
                    "recent_win_pct": recent_pct,
                    "power_score": round(power_score, 2),
                    "division_rank": team_record.get("divisionRank"),
                    "league_rank": team_record.get("leagueRank"),
                }
            )

    rankings.sort(
        key=lambda item: (
            item["power_score"],
            item["run_differential"],
            item["wins"],
        ),
        reverse=True,
    )

    for index, item in enumerate(rankings, start=1):
        item["rank"] = index

    return {
        "season": season,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "rankings": rankings,
    }



def _resolve_team(team_id: int) -> dict[str, Any]:
    data = _get_json(f"{MLB_STATS_API}/teams/{team_id}")
    items = data.get("teams", [])
    if not items:
        raise HTTPException(status_code=404, detail="MLB team not found.")
    return items[0]


def _completed_game_for_team(
    game: dict[str, Any],
    team_id: int,
) -> dict[str, Any] | None:
    if game.get("status", {}).get("abstractGameState") != "Final":
        return None

    teams = game.get("teams", {})
    away = teams.get("away", {})
    home = teams.get("home", {})
    away_id = away.get("team", {}).get("id")
    home_id = home.get("team", {}).get("id")

    if team_id not in (away_id, home_id):
        return None

    is_home = home_id == team_id
    own = home if is_home else away
    opponent = away if is_home else home
    runs_for = int(own.get("score", 0) or 0)
    runs_against = int(opponent.get("score", 0) or 0)

    return {
        "game_pk": game.get("gamePk"),
        "date": game.get("officialDate"),
        "opponent": opponent.get("team", {}).get("name", "Unknown"),
        "home": is_home,
        "runs_for": runs_for,
        "runs_against": runs_against,
        "result": "W" if runs_for > runs_against else "L",
        "run_differential": runs_for - runs_against,
        "venue": game.get("venue", {}).get("name"),
    }


@app.get("/team-analytics/{team_id}")
def team_analytics(
    team_id: int,
    days: int = Query(default=60, ge=14, le=120),
) -> dict[str, Any]:
    team = _resolve_team(team_id)
    end_date = date_type.today()
    start_date = end_date - timedelta(days=days)

    schedule_data = _get_json(
        f"{MLB_STATS_API}/schedule",
        {
            "sportId": 1,
            "teamId": team_id,
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "hydrate": "team,venue",
        },
    )

    completed: list[dict[str, Any]] = []
    for date_block in schedule_data.get("dates", []):
        for game in date_block.get("games", []):
            result = _completed_game_for_team(game, team_id)
            if result:
                completed.append(result)

    completed.sort(key=lambda game: game["date"] or "")
    recent = completed[-30:]
    wins = sum(game["result"] == "W" for game in recent)
    losses = len(recent) - wins
    runs_for = sum(game["runs_for"] for game in recent)
    runs_against = sum(game["runs_against"] for game in recent)
    home_games = [game for game in recent if game["home"]]
    road_games = [game for game in recent if not game["home"]]
    home_wins = sum(game["result"] == "W" for game in home_games)
    road_wins = sum(game["result"] == "W" for game in road_games)

    streak_result = ""
    streak_count = 0
    for game in reversed(recent):
        if not streak_result:
            streak_result = game["result"]
            streak_count = 1
        elif game["result"] == streak_result:
            streak_count += 1
        else:
            break

    rolling = []
    for window in (5, 10, 20, 30):
        sample = recent[-window:]
        if not sample:
            continue
        sample_wins = sum(game["result"] == "W" for game in sample)
        scored = sum(game["runs_for"] for game in sample)
        allowed = sum(game["runs_against"] for game in sample)
        rolling.append({
            "window": len(sample),
            "wins": sample_wins,
            "losses": len(sample) - sample_wins,
            "win_pct": sample_wins / len(sample),
            "runs_per_game": scored / len(sample),
            "runs_allowed_per_game": allowed / len(sample),
            "run_differential_per_game": (scored - allowed) / len(sample),
        })

    return {
        "team": {
            "id": team.get("id"),
            "name": team.get("name"),
            "abbreviation": team.get("abbreviation"),
            "division": team.get("division", {}).get("name"),
            "league": team.get("league", {}).get("name"),
            "venue": team.get("venue", {}).get("name"),
            "logo": _logo_url(team.get("id")),
        },
        "period": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
            "completed_games": len(recent),
        },
        "summary": {
            "wins": wins,
            "losses": losses,
            "win_pct": wins / len(recent) if recent else 0.0,
            "runs_per_game": runs_for / len(recent) if recent else 0.0,
            "runs_allowed_per_game": runs_against / len(recent) if recent else 0.0,
            "run_differential": runs_for - runs_against,
            "home_record": f"{home_wins}-{len(home_games) - home_wins}",
            "road_record": f"{road_wins}-{len(road_games) - road_wins}",
            "streak": f"{streak_result}{streak_count}" if streak_result else "—",
        },
        "rolling": rolling,
        "trend": [{
            "date": game["date"],
            "result": game["result"],
            "runs_for": game["runs_for"],
            "runs_against": game["runs_against"],
            "run_differential": game["run_differential"],
        } for game in recent[-15:]],
        "recent_games": list(reversed(recent[-10:])),
    }



@app.get("/player-props")
def player_props(
    date: str | None = Query(default=None),
    limit: int = Query(default=60, ge=1, le=150),
) -> dict[str, Any]:
    target_date = date or date_type.today().isoformat()
    try:
        datetime.strptime(target_date, "%Y-%m-%d")
    except ValueError as error:
        raise HTTPException(status_code=400, detail="Date must use YYYY-MM-DD.") from error
    props = _build_daily_props(target_date, limit)
    return {"date": target_date, "count": len(props), "props": props, "methodology": "Season per-game rates with a transparent probability curve. Lines are suggested reference points, not live sportsbook odds."}


@app.post("/analyze-prop")
def analyze_prop(request: PropAnalysisRequest) -> dict[str, Any]:
    scale = 1.5 if "Strikeout" in request.market else .8 if request.market in {"Hits", "Total Bases"} else .6
    over_probability = _normal_over_probability(request.projection, request.line, scale)
    under_probability = 1-over_probability
    over_implied = _american_implied(request.over_odds)
    under_implied = _american_implied(request.under_odds)
    over_edge = over_probability-over_implied
    under_edge = under_probability-under_implied
    side = "OVER" if over_edge > under_edge else "UNDER"
    probability = over_probability if side == "OVER" else under_probability
    odds = request.over_odds if side == "OVER" else request.under_odds
    decimal_odds = _american_to_decimal(odds)
    ev = probability * (decimal_odds-1) - (1-probability)
    return {
        "player": request.player, "market": request.market, "line": request.line,
        "projection": request.projection, "recommendation": side if max(over_edge,under_edge)>=.02 else "PASS",
        "over_probability": round(over_probability*100,1), "under_probability": round(under_probability*100,1),
        "over_edge": round(over_edge*100,1), "under_edge": round(under_edge*100,1),
        "fair_over_odds": _fair_american(over_probability), "fair_under_odds": _fair_american(under_probability),
        "expected_value": round(ev*100,1), "confidence": _confidence_label(probability),
    }



@app.post("/grade-predictions")
def grade_saved_predictions() -> dict[str, Any]:
    history = _read_history()
    graded, changed = grade_predictions(history, schedule)
    if changed:
        _write_history(graded)
        import_legacy_history(graded)
    return {"graded": changed, "performance": build_performance(graded)}


@app.get("/model-performance")
def model_performance(refresh: bool = Query(default=True)) -> dict[str, Any]:
    history = _read_history()
    if refresh:
        history, changed = grade_predictions(history, schedule)
        if changed:
            _write_history(history)
    return build_performance(history)


@app.get("/model-lab")
def model_lab() -> dict[str, Any]:
    history = _read_history()
    graded, changed = grade_predictions(history, schedule)
    if changed:
        _write_history(graded)
    return model_lab_payload(build_performance(graded))


@app.get("/weather")
def weather_center(game_date: str = Query(default_factory=lambda: date_type.today().isoformat(), alias="date")) -> dict[str, Any]:
    slate = schedule(game_date)
    return {"date": game_date, "games": [{**game, "weather": weather_for_game(game)} for game in slate["games"]]}

@app.get("/prediction-history")
def prediction_history(
    limit: int = Query(default=50, ge=1, le=250),
    team: str | None = Query(default=None),
    confidence: str | None = Query(default=None),
    result: str | None = Query(default=None),
) -> dict[str, Any]:
    predictions = list_sqlite_predictions(limit=limit, team=team, confidence=confidence, result=result)
    return {"total": len(predictions), "predictions": predictions, "summary": database_summary()}


@app.delete("/prediction-history")
def clear_prediction_history() -> dict[str, Any]:
    _write_history([])
    clear_sqlite_predictions()
    return {"status": "cleared", "message": "Prediction history has been cleared."}

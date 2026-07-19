"""Explainable matchup intelligence for Strikers.

The module translates the existing Prediction Engine inputs into transparent,
directional factor scores. It does not replace the core prediction model; it
explains the data signals that support or oppose the selected side.
"""
from __future__ import annotations

from typing import Any


def _num(source: dict[str, Any], key: str) -> float | None:
    try:
        value = source.get(key)
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _factor(
    name: str,
    home_points: float,
    away_name: str,
    home_name: str,
    detail: str,
    available: bool = True,
) -> dict[str, Any]:
    points = round(_clamp(home_points, -10.0, 10.0), 1) if available else 0.0
    favored = home_name if points > 0.15 else away_name if points < -0.15 else "Even"
    return {
        "name": name,
        "home_points": points,
        "away_points": round(-points, 1),
        "favored_team": favored,
        "strength": round(abs(points), 1),
        "detail": detail,
        "available": available,
    }


def build_model_intelligence(payload: dict[str, Any]) -> dict[str, Any]:
    prediction = payload["prediction"]
    away = payload["away_team"]
    home = payload["home_team"]
    away_pitcher = payload["away_pitcher"]
    home_pitcher = payload["home_pitcher"]
    away_name = payload["matchup"]["away"]
    home_name = payload["matchup"]["home"]

    factors: list[dict[str, Any]] = []

    away_sp_era = _num(away_pitcher, "era")
    home_sp_era = _num(home_pitcher, "era")
    sp_available = away_sp_era is not None and home_sp_era is not None
    sp_points = (away_sp_era - home_sp_era) * 1.6 if sp_available else 0.0
    factors.append(_factor(
        "Starting pitcher", sp_points, away_name, home_name,
        f"{home_pitcher.get('name', 'Home starter')} {home_sp_era:.2f} ERA vs. {away_pitcher.get('name', 'Away starter')} {away_sp_era:.2f} ERA" if sp_available else "One or both probable starters lack usable season data.",
        sp_available,
    ))

    away_ops, home_ops = _num(away, "ops"), _num(home, "ops")
    away_rpg, home_rpg = _num(away, "runs_per_game"), _num(home, "runs_per_game")
    offense_available = None not in (away_ops, home_ops, away_rpg, home_rpg)
    offense_points = ((home_ops - away_ops) * 35 + (home_rpg - away_rpg) * 1.2) if offense_available else 0.0
    factors.append(_factor(
        "Offense", offense_points, away_name, home_name,
        f"OPS {home_ops:.3f} vs. {away_ops:.3f}; runs/game {home_rpg:.2f} vs. {away_rpg:.2f}" if offense_available else "Complete team offense data is unavailable.",
        offense_available,
    ))

    away_era, home_era = _num(away, "era"), _num(home, "era")
    away_whip, home_whip = _num(away, "whip"), _num(home, "whip")
    pitching_available = None not in (away_era, home_era, away_whip, home_whip)
    pitching_points = ((away_era - home_era) * 1.0 + (away_whip - home_whip) * 3.0) if pitching_available else 0.0
    factors.append(_factor(
        "Team pitching", pitching_points, away_name, home_name,
        f"ERA {home_era:.2f} vs. {away_era:.2f}; WHIP {home_whip:.2f} vs. {away_whip:.2f}" if pitching_available else "Complete staff pitching data is unavailable.",
        pitching_available,
    ))

    away_recent, home_recent = _num(away, "recent_win_pct"), _num(home, "recent_win_pct")
    away_rd, home_rd = _num(away, "recent_run_differential_per_game"), _num(home, "recent_run_differential_per_game")
    recent_available = None not in (away_recent, home_recent, away_rd, home_rd)
    recent_points = ((home_recent - away_recent) * 12 + (home_rd - away_rd) * 1.15) if recent_available else 0.0
    factors.append(_factor(
        "Recent form", recent_points, away_name, home_name,
        f"Recent win rate {home_recent*100:.0f}% vs. {away_recent*100:.0f}%; run differential {home_rd:+.2f} vs. {away_rd:+.2f}" if recent_available else "Recent-form sample is incomplete.",
        recent_available,
    ))

    away_wp, home_wp = _num(away, "win_pct"), _num(home, "win_pct")
    season_available = away_wp is not None and home_wp is not None
    season_points = (home_wp - away_wp) * 12 if season_available else 0.0
    factors.append(_factor(
        "Season strength", season_points, away_name, home_name,
        f"Season win percentage {home_wp*100:.1f}% vs. {away_wp*100:.1f}%" if season_available else "Season records are unavailable.",
        season_available,
    ))

    factors.append(_factor(
        "Home field", 2.4, away_name, home_name,
        f"{home_name} receives the engine's standard home-field adjustment.", True,
    ))

    away_probability = float(prediction["away_probability"])
    home_probability = float(prediction["home_probability"])
    winner = str(prediction["winner"])
    loser = home_name if winner == away_name else away_name
    winner_probability = max(away_probability, home_probability)
    edge = abs(away_probability - home_probability)

    sorted_factors = sorted(factors, key=lambda item: item["strength"], reverse=True)
    advantages = [
        f"{item['favored_team']}: {item['name']} ({item['strength']:.1f} pts) — {item['detail']}"
        for item in sorted_factors
        if item["favored_team"] == winner and item["strength"] >= 0.5
    ]
    opposing = [
        f"{item['favored_team']}: {item['name']} ({item['strength']:.1f} pts) — {item['detail']}"
        for item in sorted_factors
        if item["favored_team"] == loser and item["strength"] >= 0.5
    ]

    unavailable = [item["name"] for item in factors if not item["available"]]
    risks = opposing[:3]
    if edge < 6:
        risks.append("The probability gap is narrow enough that lineup news can flip the preferred side.")
    if unavailable:
        risks.append(f"Incomplete inputs: {', '.join(unavailable)}.")

    volatility = round(_clamp(48 - edge * 1.5 + len(risks) * 5, 10, 85), 0)
    upset_chance = round(100 - winner_probability, 1)
    if winner_probability >= 70:
        grade, action = "A", "Moneyline candidate"
    elif winner_probability >= 64:
        grade, action = "B+", "Playable lean"
    elif winner_probability >= 58:
        grade, action = "B-", "Small lean only"
    else:
        grade, action = "C", "Pass"

    lead = advantages[0] if advantages else "No single factor creates a dominant statistical edge."
    counter = risks[0] if risks else f"No major factor strongly supports {loser}."
    report = (
        f"Strikers projects {winner} at {winner_probability:.1f}% in this matchup. "
        f"The strongest supporting signal is {lead.lower()} "
        f"The main counterweight is {counter.lower()} "
        f"With an estimated volatility score of {int(volatility)}/100, the recommended posture is {action.lower()}."
    )

    return {
        "headline": f"{winner} holds the model's overall matchup advantage.",
        "summary": report,
        "game_report": report,
        "grade": grade,
        "edge_points": round(edge, 1),
        "advantages": advantages[:5],
        "risks": risks[:4],
        "watch_items": [
            "Confirm probable starters and posted lineups.",
            "Review bullpen availability after the previous two games.",
            "Re-check weather and venue roof status near first pitch.",
        ],
        "recommended_action": action,
        "disclaimer": "Informational model output only; it does not include live sportsbook prices or every late-breaking change.",
        "factors": factors,
        "risk": {
            "level": "Low" if volatility <= 30 else "Moderate" if volatility <= 55 else "High",
            "volatility": int(volatility),
            "upset_chance": upset_chance,
            "confidence": round(winner_probability, 1),
        },
        "model_version": "7.0-explainable",
    }


def model_lab_payload(performance: dict[str, Any]) -> dict[str, Any]:
    summary = performance.get("summary", {})
    return {
        "engine": "Prediction Engine 7.0",
        "architecture": "Transparent weighted-factor model",
        "status": "Explainable model layer active",
        "games_evaluated": int(summary.get("graded_predictions", 0) or 0),
        "accuracy": float(summary.get("accuracy", 0) or 0),
        "roi": float(summary.get("roi", 0) or 0),
        "units": float(summary.get("units", 0) or 0),
        "calibration": "Building sample" if int(summary.get("graded_predictions", 0) or 0) < 50 else "Tracked",
        "features": [
            {"name": "Starting pitcher", "importance": 26, "description": "Starter ERA, WHIP, and availability"},
            {"name": "Offense", "importance": 21, "description": "OPS and runs scored per game"},
            {"name": "Team pitching", "importance": 18, "description": "Staff ERA and WHIP"},
            {"name": "Recent form", "importance": 15, "description": "Recent win rate and run differential"},
            {"name": "Season strength", "importance": 12, "description": "Overall winning percentage"},
            {"name": "Home field", "importance": 8, "description": "Standard home advantage"},
        ],
        "limitations": [
            "Weights are transparent heuristics, not a trained machine-learning model.",
            "Lineups, injuries, bullpen availability, and odds may change after a prediction is created.",
            "Feature importance describes configured influence, not causal impact.",
        ],
    }

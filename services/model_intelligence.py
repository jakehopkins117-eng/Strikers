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
        "Starting pitching", sp_points, away_name, home_name,
        f"{home_pitcher.get('name', 'Home starter')} owns a {home_sp_era:.2f} ERA compared with {away_pitcher.get('name', 'Away starter')} at {away_sp_era:.2f}." if sp_available else "One or both probable starters lack a reliable season sample.",
        sp_available,
    ))

    away_ops, home_ops = _num(away, "ops"), _num(home, "ops")
    away_rpg, home_rpg = _num(away, "runs_per_game"), _num(home, "runs_per_game")
    offense_available = None not in (away_ops, home_ops, away_rpg, home_rpg)
    offense_points = ((home_ops - away_ops) * 35 + (home_rpg - away_rpg) * 1.2) if offense_available else 0.0
    factors.append(_factor(
        "Offensive production", offense_points, away_name, home_name,
        f"{home_name} carries a {home_ops:.3f} OPS and {home_rpg:.2f} runs per game; {away_name} enters at {away_ops:.3f} and {away_rpg:.2f}." if offense_available else "Complete team offensive data is unavailable.",
        offense_available,
    ))

    away_era, home_era = _num(away, "era"), _num(home, "era")
    away_whip, home_whip = _num(away, "whip"), _num(home, "whip")
    pitching_available = None not in (away_era, home_era, away_whip, home_whip)
    pitching_points = ((away_era - home_era) * 1.0 + (away_whip - home_whip) * 3.0) if pitching_available else 0.0
    factors.append(_factor(
        "Staff run prevention", pitching_points, away_name, home_name,
        f"{home_name} posts a {home_era:.2f} team ERA and {home_whip:.2f} WHIP versus {away_name} at {away_era:.2f} and {away_whip:.2f}." if pitching_available else "Complete staff pitching data is unavailable.",
        pitching_available,
    ))

    away_recent, home_recent = _num(away, "recent_win_pct"), _num(home, "recent_win_pct")
    away_rd, home_rd = _num(away, "recent_run_differential_per_game"), _num(home, "recent_run_differential_per_game")
    recent_available = None not in (away_recent, home_recent, away_rd, home_rd)
    recent_points = ((home_recent - away_recent) * 12 + (home_rd - away_rd) * 1.15) if recent_available else 0.0
    factors.append(_factor(
        "Recent form", recent_points, away_name, home_name,
        f"Recent win rate favors {home_name} at {home_recent*100:.0f}% versus {away_recent*100:.0f}%, with run differential at {home_rd:+.2f} and {away_rd:+.2f} per game." if recent_available else "The recent-form sample is incomplete.",
        recent_available,
    ))

    away_wp, home_wp = _num(away, "win_pct"), _num(home, "win_pct")
    season_available = away_wp is not None and home_wp is not None
    season_points = (home_wp - away_wp) * 12 if season_available else 0.0
    factors.append(_factor(
        "Season strength", season_points, away_name, home_name,
        f"{home_name} enters with a {home_wp*100:.1f}% win rate compared with {away_name} at {away_wp*100:.1f}%." if season_available else "Season records are unavailable.",
        season_available,
    ))

    factors.append(_factor(
        "Home-field context", 2.4, away_name, home_name,
        f"{home_name} receives the engine's standard home-field adjustment.", True,
    ))

    away_probability = float(prediction["away_probability"])
    home_probability = float(prediction["home_probability"])
    winner = str(prediction["winner"])
    loser = home_name if winner == away_name else away_name
    winner_probability = max(away_probability, home_probability)
    edge = abs(away_probability - home_probability)

    sorted_factors = sorted(factors, key=lambda item: item["strength"], reverse=True)
    winner_factors = [item for item in sorted_factors if item["favored_team"] == winner and item["available"]]
    loser_factors = [item for item in sorted_factors if item["favored_team"] == loser and item["available"]]

    advantages = [
        f"{item['name']}: {item['detail']}"
        for item in winner_factors if item["strength"] >= 0.5
    ]
    risks = [
        f"{item['name']}: {item['detail']}"
        for item in loser_factors if item["strength"] >= 0.5
    ]

    unavailable = [item["name"] for item in factors if not item["available"]]
    if edge < 6:
        risks.append("The projected margin is narrow enough that confirmed lineups or a pitching change could reverse the preferred side.")
    if unavailable:
        risks.append(f"Incomplete inputs remain for {', '.join(unavailable)}.")

    volatility = round(_clamp(48 - edge * 1.5 + len(risks) * 5, 10, 85), 0)
    upset_chance = round(100 - winner_probability, 1)
    if winner_probability >= 70:
        grade, action = "A", "Strong model position"
    elif winner_probability >= 64:
        grade, action = "B+", "Clear matchup lean"
    elif winner_probability >= 58:
        grade, action = "B-", "Measured lean"
    else:
        grade, action = "C", "Limited separation"

    top_support = winner_factors[0] if winner_factors else None
    top_counter = loser_factors[0] if loser_factors else None
    support_name = top_support["name"].lower() if top_support else "the broader statistical profile"
    counter_name = top_counter["name"].lower() if top_counter else "late lineup and availability news"

    if winner_probability >= 70:
        confidence_phrase = "a strong statistical position"
    elif winner_probability >= 64:
        confidence_phrase = "a clear matchup advantage"
    elif winner_probability >= 58:
        confidence_phrase = "a modest but meaningful edge"
    else:
        confidence_phrase = "a narrow lean in a competitive matchup"

    summary = (
        f"{winner} enters with {confidence_phrase}, with {support_name} providing the clearest separation. "
        f"{loser} remains competitive because of {counter_name}, so the projection is best viewed as a measured advantage rather than a certainty."
    )

    away_sp_name = away_pitcher.get("name") or f"the {away_name} starter"
    home_sp_name = home_pitcher.get("name") or f"the {home_name} starter"
    key_matchup = (
        f"The central matchup is {home_sp_name} against the {away_name} lineup, with {away_sp_name} facing the {home_name} offense on the other side. "
        "Whichever starter limits early traffic is more likely to hand the game to the stronger bullpen in favorable situations."
    )

    if top_support:
        game_script = (
            f"Strikers expects {winner} to build its advantage through {top_support['name'].lower()}. "
            f"The preferred path is a controlled first five innings followed by favorable bullpen matchups. "
            f"{loser}'s best route is to create early baserunners, raise the opposing starter's pitch count, and prevent the favored side from managing the game from ahead."
        )
    else:
        game_script = (
            f"This matchup projects to remain close into the middle innings. {winner} owns the slight overall edge, but no single category creates decisive separation. "
            "Bullpen execution, defensive mistakes, and timely extra-base hits are likely to determine the result."
        )

    if top_counter:
        primary_concern = (
            f"The main concern for the {winner} projection is {top_counter['name'].lower()}. "
            f"That advantage gives {loser} a credible path to outperform the model, particularly if the game remains within one run entering the late innings."
        )
    elif edge < 6:
        primary_concern = (
            "The probability gap is small, leaving the recommendation sensitive to confirmed lineups, pitcher changes, and bullpen availability. "
            "A single late update could materially change the preferred side."
        )
    else:
        primary_concern = (
            f"The largest remaining risk is normal baseball variance. Even with the stronger profile, {winner} can lose the matchup through poor sequencing, defensive mistakes, or an early pitching exit."
        )

    confidence_explanation = (
        f"The {grade} grade reflects a {edge:.1f}-point probability gap and {int(volatility)}/100 estimated volatility. "
        f"Confidence is strengthened by {support_name}. It is limited by {counter_name} and an upset probability of {upset_chance:.1f}%."
    )

    swing_factor = (
        "The projection is most sensitive to a starting-pitcher change, an important hitter being removed from the lineup, or unexpected bullpen unavailability. "
        f"Because the current edge is {edge:.1f} points, those updates matter more than small changes in season-long averages."
    )

    if winner_probability >= 64:
        bottom_line = (
            f"{winner} deserves to be favored and owns the cleaner overall profile. The model identifies a real advantage, but the remaining upset risk supports disciplined confidence rather than an aggressive all-or-nothing position."
        )
    elif winner_probability >= 58:
        bottom_line = (
            f"The data supports {winner}, but the margin is not large enough to treat the matchup as one-sided. This is a reasonable lean with identifiable strengths and a meaningful path for {loser} to stay competitive."
        )
    else:
        bottom_line = (
            f"{winner} holds only a slight edge. The matchup is close enough that price, confirmed lineups, and late pitching news should carry nearly as much weight as the initial model preference."
        )

    report = (
        f"{winner} is the preferred side at {winner_probability:.1f}%. {support_name.capitalize()} is the primary advantage, while {counter_name} is the most important counterweight. "
        f"With a {upset_chance:.1f}% upset probability, the recommendation is a quantified lean—not a guaranteed outcome."
    )

    return {
        "headline": f"{winner} owns the more complete matchup profile.",
        "summary": summary,
        "game_report": report,
        "primary_concern": primary_concern,
        "bottom_line": bottom_line,
        "key_matchup": key_matchup,
        "game_script": game_script,
        "confidence_explanation": confidence_explanation,
        "swing_factor": swing_factor,
        "grade": grade,
        "edge_points": round(edge, 1),
        "advantages": advantages[:4],
        "risks": risks[:4],
        "watch_items": [
            "Confirm both probable starters and the official batting orders.",
            "Review high-leverage bullpen usage from the previous two games.",
            "Re-check weather, wind direction, and roof status near first pitch.",
        ],
        "recommended_action": action,
        "disclaimer": "Informational model analysis only. Late lineup changes, pitching scratches, bullpen availability, and market prices can materially alter the outlook.",
        "factors": factors,
        "risk": {
            "level": "Low" if volatility <= 30 else "Moderate" if volatility <= 55 else "High",
            "volatility": int(volatility),
            "upset_chance": upset_chance,
            "confidence": round(winner_probability, 1),
        },
        "model_version": "7.2-editorial",
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

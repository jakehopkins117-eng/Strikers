"""Sportsbook price evaluation for Strikers.

Compares model probabilities with user-supplied American odds and produces a
transparent value score, expected value estimate, and conservative stake size.
Strikers never invents sportsbook prices.
"""
from __future__ import annotations

from typing import Any


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def implied_probability(american_odds: int) -> float:
    if american_odds == 0:
        raise ValueError("American odds cannot be zero.")
    if american_odds > 0:
        return 100.0 / (american_odds + 100.0)
    return abs(american_odds) / (abs(american_odds) + 100.0)


def decimal_odds(american_odds: int) -> float:
    if american_odds == 0:
        raise ValueError("American odds cannot be zero.")
    if american_odds > 0:
        return 1.0 + american_odds / 100.0
    return 1.0 + 100.0 / abs(american_odds)


def fair_american(probability: float) -> int:
    p = _clamp(probability, 0.001, 0.999)
    if p >= 0.5:
        return round(-(p / (1.0 - p)) * 100.0)
    return round(((1.0 - p) / p) * 100.0)


def expected_value_percent(model_probability: float, american_odds: int) -> float:
    return (model_probability * decimal_odds(american_odds) - 1.0) * 100.0


def kelly_fraction(model_probability: float, american_odds: int) -> float:
    """Return full Kelly fraction, floored at zero for negative-value bets."""
    decimal = decimal_odds(american_odds)
    net_profit = decimal - 1.0
    loss_probability = 1.0 - model_probability
    raw = (net_profit * model_probability - loss_probability) / net_profit
    return max(0.0, raw)


def suggested_units(model_probability: float, american_odds: int) -> float:
    """Conservative quarter-Kelly staking, capped at two units.

    One unit is intended to equal roughly 1% of a user's bankroll. The result is
    rounded to quarter-unit increments and negative-value bets return zero.
    """
    quarter_kelly_bankroll_pct = kelly_fraction(model_probability, american_odds) * 25.0
    units = _clamp(quarter_kelly_bankroll_pct, 0.0, 2.0)
    return round(units * 4.0) / 4.0


def bet_quality_score(edge_points: float, ev_percent: float, model_probability: float) -> int:
    """Create a transparent 0-100 price-quality score.

    Price edge and EV drive most of the score. Model probability contributes a
    smaller stability component so a tiny edge on a very uncertain side is not
    ranked like a stronger, better-supported wager.
    """
    edge_component = _clamp(edge_points / 10.0, 0.0, 1.0) * 45.0
    ev_component = _clamp(ev_percent / 15.0, 0.0, 1.0) * 40.0
    stability_component = _clamp((model_probability - 0.50) / 0.20, 0.0, 1.0) * 15.0
    return round(edge_component + ev_component + stability_component)


def _rating(score: int, edge_points: float, ev_percent: float) -> tuple[str, str]:
    if ev_percent <= 0 or edge_points <= 0:
        return "PASS", "Pass"
    if score >= 85 and edge_points >= 6.0:
        return "ELITE VALUE", "Consider"
    if score >= 70 and edge_points >= 4.0:
        return "STRONG VALUE", "Consider"
    if score >= 55 and edge_points >= 2.0:
        return "VALUE", "Consider small"
    if score >= 40:
        return "LEAN", "Lean only"
    return "PASS", "Pass"


def evaluate_moneyline(
    *,
    away_team: str,
    home_team: str,
    away_probability: float,
    home_probability: float,
    away_odds: int | None,
    home_odds: int | None,
) -> dict[str, Any]:
    sides: list[dict[str, Any]] = []
    for team, probability_percent, odds in (
        (away_team, away_probability, away_odds),
        (home_team, home_probability, home_odds),
    ):
        probability = probability_percent / 100.0
        if odds is None:
            sides.append({
                "team": team,
                "model_probability": round(probability_percent, 2),
                "odds": None,
                "implied_probability": None,
                "edge_points": None,
                "fair_odds": fair_american(probability),
                "expected_value": None,
                "quality_score": None,
                "kelly_fraction": None,
                "suggested_units": None,
                "rating": "NO PRICE",
                "recommendation": "Enter odds",
            })
            continue

        implied = implied_probability(odds)
        edge = (probability - implied) * 100.0
        ev = expected_value_percent(probability, odds)
        score = bet_quality_score(edge, ev, probability)
        rating, recommendation = _rating(score, edge, ev)
        units = suggested_units(probability, odds) if ev > 0 else 0.0
        sides.append({
            "team": team,
            "model_probability": round(probability_percent, 2),
            "odds": odds,
            "implied_probability": round(implied * 100.0, 2),
            "edge_points": round(edge, 2),
            "fair_odds": fair_american(probability),
            "expected_value": round(ev, 2),
            "quality_score": score,
            "kelly_fraction": round(kelly_fraction(probability, odds) * 100.0, 2),
            "suggested_units": units,
            "rating": rating,
            "recommendation": recommendation,
        })

    priced = [side for side in sides if side["odds"] is not None]
    positive = [side for side in priced if (side["expected_value"] or 0) > 0]
    best = max(positive, key=lambda item: item["quality_score"], default=None)
    return {
        "market": "Moneyline",
        "status": "ready" if len(priced) == 2 else "needs_prices",
        "sides": sides,
        "best_value": best,
        "staking_method": "Quarter Kelly, capped at 2 units",
        "unit_definition": "1 unit is approximately 1% of bankroll",
        "disclaimer": (
            "Price comparison is informational. Odds must be entered by the user, "
            "can change rapidly, and no wager is guaranteed."
        ),
    }

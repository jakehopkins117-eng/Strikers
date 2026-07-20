"""Sportsbook price evaluation for Strikers.

The module compares model probabilities with user-supplied American odds. It
never fetches or invents sportsbook prices.
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


def _rating(edge_points: float, ev_percent: float) -> tuple[str, str]:
    if edge_points >= 8.0 and ev_percent >= 10.0:
        return "STRONG VALUE", "Consider"
    if edge_points >= 4.0 and ev_percent >= 4.0:
        return "VALUE", "Consider"
    if edge_points >= 1.5 and ev_percent > 0:
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
                "rating": "NO PRICE",
                "recommendation": "Enter odds",
            })
            continue

        implied = implied_probability(odds)
        edge = (probability - implied) * 100.0
        ev = expected_value_percent(probability, odds)
        rating, recommendation = _rating(edge, ev)
        sides.append({
            "team": team,
            "model_probability": round(probability_percent, 2),
            "odds": odds,
            "implied_probability": round(implied * 100.0, 2),
            "edge_points": round(edge, 2),
            "fair_odds": fair_american(probability),
            "expected_value": round(ev, 2),
            "rating": rating,
            "recommendation": recommendation,
        })

    priced = [side for side in sides if side["odds"] is not None]
    best = max(priced, key=lambda item: item["expected_value"], default=None)
    return {
        "market": "Moneyline",
        "status": "ready" if len(priced) == 2 else "needs_prices",
        "sides": sides,
        "best_value": best,
        "disclaimer": "Price comparison only. Odds must be entered by the user and can change rapidly.",
    }

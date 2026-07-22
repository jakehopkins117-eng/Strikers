"""Strikers v3.5 sportsbook edge and Bet Score engine."""

from __future__ import annotations

from typing import Any

from services.odds import american_decimal


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _side_context(payload: dict[str, Any], side: str) -> dict[str, Any]:
    lineup = (payload.get("lineup_intelligence") or {}).get(side, {})
    injuries = (payload.get("injury_intelligence") or {}).get(side, {})
    bullpen = payload.get(f"{side}_bullpen") or {}
    return {"lineup": lineup, "injuries": injuries, "bullpen": bullpen}


def _value_label(edge: float | None) -> str:
    if edge is None:
        return "Market unavailable"
    if edge >= 10:
        return "Elite Value"
    if edge >= 7:
        return "Strong Value"
    if edge >= 4:
        return "Moderate Value"
    if edge >= 1:
        return "Fair Line"
    return "No Value"


def _recommendation(score: int, edge: float | None) -> tuple[str, str]:
    if edge is None:
        return "NO MARKET", "Wait for sportsbook prices"
    if score >= 85 and edge >= 6:
        return "PREMIUM BET", "Large model-market disagreement with strong supporting signals"
    if score >= 72 and edge >= 3:
        return "WORTH CONSIDERING", "Positive value, but confirm lineups and price before betting"
    return "PASS", "The current price does not provide enough model edge"


def _build_side(payload: dict[str, Any], sportsbook: dict[str, Any], side: str) -> dict[str, Any]:
    team = payload["matchup"][side]
    model_probability = _number(payload["prediction"][f"{side}_probability"])
    market_side = ((sportsbook.get("moneyline") or {}).get(side) or {})
    best = market_side.get("best") or {}
    best_odds = best.get("odds")
    fair_market = market_side.get("fair_market_probability")
    edge = round(model_probability - _number(fair_market), 2) if fair_market is not None else None

    expected_value = None
    if best_odds is not None:
        expected_value = round((model_probability / 100.0) * american_decimal(best_odds) - 1.0, 4)

    context = _side_context(payload, side)
    lineup = context["lineup"]
    bullpen = context["bullpen"]
    injuries = context["injuries"]
    confirmed = bool(lineup.get("confirmed"))
    lineup_strength = _number(lineup.get("strength_score"), 50.0)
    bullpen_score = _number(bullpen.get("availability_score"), 50.0)
    injury_penalty = _number(injuries.get("penalty_points"), 0.0)
    market_depth = len(market_side.get("prices") or [])

    edge_component = _clamp(((edge or 0.0) + 2.0) / 14.0 * 45.0, 0.0, 45.0)
    confidence_component = _clamp((model_probability - 50.0) / 25.0 * 25.0, 0.0, 25.0)
    lineup_component = _clamp((lineup_strength - 35.0) / 65.0 * 10.0, 0.0, 10.0)
    bullpen_component = _clamp(bullpen_score / 100.0 * 8.0, 0.0, 8.0)
    certainty_component = (5.0 if confirmed else 2.0) + _clamp(market_depth / 6.0 * 5.0, 0.0, 5.0)
    injury_component = _clamp(7.0 - injury_penalty, 0.0, 7.0)
    score = int(round(_clamp(edge_component + confidence_component + lineup_component + bullpen_component + certainty_component + injury_component, 0.0, 100.0)))

    label = _value_label(edge)
    recommendation, recommendation_detail = _recommendation(score, edge)
    reasons: list[str] = []
    if edge is not None:
        reasons.append(f"Strikers is {edge:+.1f} percentage points above the no-vig market.")
    if best_odds is not None:
        reasons.append(f"Best available price is {best_odds:+d} at {best.get('bookmaker', 'a listed sportsbook')}.")
    if confirmed:
        reasons.append("The batting order is confirmed.")
    else:
        reasons.append("The lineup is still projected, which lowers certainty.")
    if bullpen_score >= 65:
        reasons.append("Bullpen availability supports the position.")
    elif bullpen_score < 45:
        reasons.append("Bullpen fatigue is a meaningful risk.")
    if injury_penalty >= 3:
        reasons.append("Injury impact lowers the score.")
    if market_depth < 2:
        reasons.append("Limited sportsbook coverage makes the market estimate less reliable.")

    return {
        "team": team,
        "side": side,
        "model_probability": round(model_probability, 2),
        "market_probability": fair_market,
        "consensus_implied_probability": market_side.get("consensus_implied_probability"),
        "edge_points": edge,
        "best_odds": best_odds,
        "best_bookmaker": best.get("bookmaker"),
        "best_link": best.get("link"),
        "expected_value": round(expected_value * 100.0, 2) if expected_value is not None else None,
        "bet_score": score,
        "value_label": label,
        "recommendation": recommendation,
        "recommendation_detail": recommendation_detail,
        "market_depth": market_depth,
        "reasons": reasons[:5],
    }


def build_sportsbook_intelligence(payload: dict[str, Any], sportsbook: dict[str, Any]) -> dict[str, Any]:
    sides = [_build_side(payload, sportsbook, "away"), _build_side(payload, sportsbook, "home")]
    sides.sort(key=lambda item: (item["bet_score"], item["edge_points"] if item["edge_points"] is not None else -999), reverse=True)
    best = sides[0]
    return {
        "available": bool(sportsbook.get("available")),
        "status": sportsbook.get("status"),
        "message": sportsbook.get("message"),
        "provider": sportsbook.get("provider", "The Odds API"),
        "event_id": sportsbook.get("event_id"),
        "commence_time": sportsbook.get("commence_time"),
        "last_update": sportsbook.get("last_update"),
        "best_value": best if best.get("edge_points") is not None else None,
        "sides": sides,
        "bookmakers": ((sportsbook.get("moneyline") or {}).get("bookmakers") or []),
        "spreads": sportsbook.get("spreads") or [],
        "totals": sportsbook.get("totals") or [],
        "quota": sportsbook.get("meta") or {},
        "disclaimer": "Odds can move at any time. Verify the current sportsbook price before placing a wager.",
    }

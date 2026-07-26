"""Feature engineering layer for Strikers Sprint 15.

This module turns the model's raw team, pitcher, bullpen, lineup, and injury
payloads into a stable set of normalized matchup features.  It does not make a
second prediction or double-count factors in the rules engine.  Its primary
purpose is to create consistent training data for calibration and future ML.
"""
from __future__ import annotations

from typing import Any


def _number(source: dict[str, Any] | None, key: str, default: float = 0.0) -> float:
    try:
        value = (source or {}).get(key)
        return float(value) if value not in (None, "") else default
    except (TypeError, ValueError):
        return default


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _gap(home: float, away: float, scale: float) -> float:
    """Return a normalized home-minus-away gap constrained to -1..1."""
    if scale <= 0:
        return 0.0
    return round(_clamp((home - away) / scale, -1.0, 1.0), 4)


def build_feature_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    away = payload.get("away_team") or {}
    home = payload.get("home_team") or {}
    away_pitcher = payload.get("away_pitcher") or {}
    home_pitcher = payload.get("home_pitcher") or {}
    away_bullpen = payload.get("away_bullpen") or {}
    home_bullpen = payload.get("home_bullpen") or {}
    lineup = payload.get("lineup_intelligence") or {}
    injuries = payload.get("injury_intelligence") or {}

    away_lineup = lineup.get("away") or {}
    home_lineup = lineup.get("home") or {}
    away_injuries = injuries.get("away") or {}
    home_injuries = injuries.get("home") or {}

    raw = {
        "season_win_pct_gap": _number(home, "win_pct") - _number(away, "win_pct"),
        "location_win_pct_gap": _number(home, "location_win_pct") - _number(away, "location_win_pct"),
        "ops_gap": _number(home, "ops") - _number(away, "ops"),
        "runs_per_game_gap": _number(home, "runs_per_game") - _number(away, "runs_per_game"),
        "team_era_gap": _number(away, "era") - _number(home, "era"),
        "team_whip_gap": _number(away, "whip") - _number(home, "whip"),
        "recent_win_pct_gap": _number(home, "recent_win_pct") - _number(away, "recent_win_pct"),
        "recent_run_diff_gap": _number(home, "recent_run_differential_per_game") - _number(away, "recent_run_differential_per_game"),
        "starter_era_gap": _number(away_pitcher, "era") - _number(home_pitcher, "era"),
        "starter_whip_gap": _number(away_pitcher, "whip") - _number(home_pitcher, "whip"),
        "bullpen_availability_gap": _number(home_bullpen, "availability_score", 75.0) - _number(away_bullpen, "availability_score", 75.0),
        "bullpen_era_gap": _number(away_bullpen, "season_era") - _number(home_bullpen, "season_era"),
        "lineup_strength_gap": _number(home_lineup, "strength_score", 65.0) - _number(away_lineup, "strength_score", 65.0),
        "top_order_ops_gap": _number(home_lineup, "top_order_ops") - _number(away_lineup, "top_order_ops"),
        "injury_penalty_gap": _number(away_injuries, "penalty_points") - _number(home_injuries, "penalty_points"),
    }

    normalized = {
        "season_form": _gap(_number(home, "win_pct"), _number(away, "win_pct"), 0.20),
        "location_form": _gap(_number(home, "location_win_pct"), _number(away, "location_win_pct"), 0.25),
        "offense_quality": _gap(_number(home, "ops"), _number(away, "ops"), 0.12),
        "run_scoring": _gap(_number(home, "runs_per_game"), _number(away, "runs_per_game"), 2.0),
        "team_run_prevention": _gap(_number(away, "era"), _number(home, "era"), 2.0),
        "recent_form": _gap(_number(home, "recent_win_pct"), _number(away, "recent_win_pct"), 0.35),
        "starter_quality": _gap(_number(away_pitcher, "era"), _number(home_pitcher, "era"), 2.5),
        "bullpen_health": _gap(_number(home_bullpen, "availability_score", 75.0), _number(away_bullpen, "availability_score", 75.0), 40.0),
        "lineup_quality": _gap(_number(home_lineup, "strength_score", 65.0), _number(away_lineup, "strength_score", 65.0), 20.0),
        "injury_health": _gap(_number(away_injuries, "penalty_points"), _number(home_injuries, "penalty_points"), 3.0),
    }

    quality_checks = {
        "both_lineups_confirmed": bool(away_lineup.get("confirmed") and home_lineup.get("confirmed")),
        "away_lineup_completeness": _number(away_lineup, "completeness", 0.0),
        "home_lineup_completeness": _number(home_lineup, "completeness", 0.0),
        "both_starters_available": bool(away_pitcher.get("available") and home_pitcher.get("available")),
        "both_bullpens_available": bool(away_bullpen.get("available") and home_bullpen.get("available")),
    }
    available_signals = sum(
        [
            quality_checks["both_lineups_confirmed"],
            quality_checks["both_starters_available"],
            quality_checks["both_bullpens_available"],
            bool(away),
            bool(home),
        ]
    )

    return {
        "version": "15.1",
        "perspective": "positive values favor the home team",
        "raw": {key: round(value, 4) for key, value in raw.items()},
        "normalized": normalized,
        "quality": quality_checks,
        "data_quality_score": round((available_signals / 5) * 100, 1),
    }

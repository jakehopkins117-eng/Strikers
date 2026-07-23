"""Conservative self-learning layer for Strikers.

The learner studies graded predictions, measures calibration and factor results,
and produces a small probability correction. It never changes the core engine's
weights directly. Corrections activate only after a meaningful sample and are
shrunk/capped to reduce overfitting.
"""
from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "data" / "self_learning_report.json"
MIN_GRADED = max(10, int(os.getenv("SELF_LEARNING_MIN_GRADED", "40")))
MIN_FACTOR_SAMPLE = max(8, int(os.getenv("SELF_LEARNING_MIN_FACTOR_SAMPLE", "15")))
MAX_CORRECTION = max(0.5, min(5.0, float(os.getenv("SELF_LEARNING_MAX_CORRECTION", "2.5"))))
ENABLED = os.getenv("SELF_LEARNING_ENABLED", "true").strip().lower() not in {"0", "false", "no", "off"}


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _predicted_probability(item: dict[str, Any]) -> float:
    return max(_number(item.get("away_probability")), _number(item.get("home_probability")))


def _factor_flags(item: dict[str, Any]) -> dict[str, bool]:
    features = item.get("learning_features") or {}
    reasons = " ".join(str(reason).lower() for reason in item.get("reasons", []))
    winner = str(item.get("winner", ""))
    return {
        "home_team_pick": winner == str(item.get("home_team", "")),
        "high_confidence_65_plus": _predicted_probability(item) >= 65.0,
        "close_game_below_57": _predicted_probability(item) < 57.0,
        "projected_margin_2_plus": abs(_number(features.get("projected_run_margin"))) >= 2.0,
        "starting_pitcher_edge": bool(features.get("starting_pitcher_edge")) or "pitcher" in reasons,
        "bullpen_edge": bool(features.get("bullpen_edge")) or "bullpen" in reasons,
        "lineup_adjustment": abs(_number(features.get("lineup_adjustment"))) >= 0.5 or "lineup" in reasons,
        "injury_adjustment": abs(_number(features.get("injury_adjustment"))) >= 0.5 or "injury" in reasons,
        "sportsbook_value": bool(features.get("sportsbook_value")) or _number((item.get("betting") or {}).get("value_ev")) > 0,
    }


def _empty_report(graded: int = 0) -> dict[str, Any]:
    return {
        "enabled": ENABLED,
        "status": "Collecting data" if graded < MIN_GRADED else "Ready",
        "graded_games": graded,
        "minimum_games": MIN_GRADED,
        "progress_percent": min(100.0, round(graded / MIN_GRADED * 100, 1)),
        "active": False,
        "probability_correction": 0.0,
        "baseline_accuracy": 0.0,
        "average_confidence": 0.0,
        "calibration_gap": 0.0,
        "factors": [],
        "recommendations": [f"Grade {max(MIN_GRADED - graded, 0)} more games before automatic calibration activates."],
        "updated_at": None,
        "safety": {
            "method": "Shrunk calibration correction",
            "maximum_adjustment_points": MAX_CORRECTION,
            "core_weights_changed": False,
        },
    }


def analyze_history(history: list[dict[str, Any]], *, persist: bool = True) -> dict[str, Any]:
    graded = [item for item in history if item.get("result") in {"win", "loss"}]
    if not graded:
        report = _empty_report(0)
        if persist:
            _write_report(report)
        return report

    wins = sum(item.get("result") == "win" for item in graded)
    baseline = wins / len(graded) * 100.0
    average_confidence = sum(_predicted_probability(item) for item in graded) / len(graded)
    calibration_gap = baseline - average_confidence

    # Shrink toward zero until the dataset becomes substantial. At 40 games,
    # only half of the observed gap is considered; it approaches full strength
    # gradually and remains capped.
    reliability = min(1.0, len(graded) / max(MIN_GRADED * 2, 1))
    raw_correction = calibration_gap * reliability
    correction = max(-MAX_CORRECTION, min(MAX_CORRECTION, raw_correction)) if len(graded) >= MIN_GRADED else 0.0

    factor_stats: dict[str, dict[str, int]] = defaultdict(lambda: {"games": 0, "wins": 0})
    for item in graded:
        won = item.get("result") == "win"
        for factor, present in _factor_flags(item).items():
            if present:
                factor_stats[factor]["games"] += 1
                factor_stats[factor]["wins"] += int(won)

    label_map = {
        "home_team_pick": "Home-team selections",
        "high_confidence_65_plus": "65%+ confidence picks",
        "close_game_below_57": "Below-57% confidence picks",
        "projected_margin_2_plus": "Projected margin of 2+ runs",
        "starting_pitcher_edge": "Starting-pitcher edge",
        "bullpen_edge": "Bullpen edge",
        "lineup_adjustment": "Lineup adjustment",
        "injury_adjustment": "Injury adjustment",
        "sportsbook_value": "Positive sportsbook value",
    }
    factor_rows: list[dict[str, Any]] = []
    for key, stats in factor_stats.items():
        accuracy = stats["wins"] / stats["games"] * 100.0 if stats["games"] else 0.0
        lift = accuracy - baseline
        reliable = stats["games"] >= MIN_FACTOR_SAMPLE
        factor_rows.append({
            "key": key,
            "label": label_map.get(key, key.replace("_", " ").title()),
            "games": stats["games"],
            "wins": stats["wins"],
            "accuracy": round(accuracy, 1),
            "lift": round(lift, 1),
            "reliable": reliable,
            "signal": "positive" if reliable and lift >= 3 else "negative" if reliable and lift <= -3 else "neutral",
        })
    factor_rows.sort(key=lambda row: (not row["reliable"], -abs(row["lift"]), -row["games"]))

    recommendations: list[str] = []
    if len(graded) < MIN_GRADED:
        recommendations.append(f"Collect {MIN_GRADED - len(graded)} more graded games before applying automatic probability calibration.")
    elif correction <= -0.5:
        recommendations.append(f"The model has been overconfident. Reduce future winning probabilities by {abs(correction):.1f} points.")
    elif correction >= 0.5:
        recommendations.append(f"The model has been conservative. Increase future winning probabilities by {correction:.1f} points.")
    else:
        recommendations.append("Confidence is currently well calibrated; no meaningful global correction is needed.")

    reliable_rows = [row for row in factor_rows if row["reliable"]]
    positive = next((row for row in reliable_rows if row["lift"] >= 3), None)
    negative = next((row for row in reliable_rows if row["lift"] <= -3), None)
    if positive:
        recommendations.append(f"Strongest observed signal: {positive['label']} ({positive['accuracy']:.1f}% across {positive['games']} games).")
    if negative:
        recommendations.append(f"Weakest observed signal: {negative['label']} ({negative['accuracy']:.1f}% across {negative['games']} games).")
    if not reliable_rows:
        recommendations.append(f"Each factor needs at least {MIN_FACTOR_SAMPLE} graded examples before it is treated as reliable.")

    report = {
        "enabled": ENABLED,
        "status": "Active" if ENABLED and len(graded) >= MIN_GRADED else "Collecting data",
        "graded_games": len(graded),
        "minimum_games": MIN_GRADED,
        "progress_percent": min(100.0, round(len(graded) / MIN_GRADED * 100, 1)),
        "active": bool(ENABLED and len(graded) >= MIN_GRADED),
        "probability_correction": round(correction, 2),
        "baseline_accuracy": round(baseline, 1),
        "average_confidence": round(average_confidence, 1),
        "calibration_gap": round(calibration_gap, 1),
        "factors": factor_rows,
        "recommendations": recommendations,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "safety": {
            "method": "Shrunk calibration correction",
            "maximum_adjustment_points": MAX_CORRECTION,
            "core_weights_changed": False,
        },
    }
    if persist:
        _write_report(report)
    return report


def _write_report(report: dict[str, Any]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp = REPORT_PATH.with_suffix(".tmp")
    temp.write_text(json.dumps(report, indent=2), encoding="utf-8")
    temp.replace(REPORT_PATH)


def learning_status() -> dict[str, Any]:
    if not REPORT_PATH.exists():
        return _empty_report(0)
    try:
        payload = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else _empty_report(0)
    except (OSError, json.JSONDecodeError):
        return _empty_report(0)


def apply_learning_adjustment(prediction: dict[str, Any], matchup: dict[str, str]) -> dict[str, Any]:
    """Apply only the persisted, globally calibrated probability correction."""
    report = learning_status()
    if not report.get("active") or not ENABLED:
        return {"applied": False, "points": 0.0, "status": report.get("status", "Collecting data")}

    points = _number(report.get("probability_correction"))
    winner = str(prediction.get("winner"))
    away = _number(prediction.get("away_probability"), 50.0)
    home = _number(prediction.get("home_probability"), 50.0)
    if winner == matchup.get("away"):
        away = max(20.0, min(80.0, away + points)); home = 100.0 - away
    else:
        home = max(20.0, min(80.0, home + points)); away = 100.0 - home

    prediction["away_probability"] = round(away, 2)
    prediction["home_probability"] = round(home, 2)
    prediction["winner"] = matchup["away"] if away >= home else matchup["home"]
    win_prob = max(away, home)
    prediction["confidence"] = "High" if win_prob >= 65 else "Moderate" if win_prob >= 57 else "Low"
    prediction["confidence_stars"] = "★★★★★" if win_prob >= 70 else "★★★★☆" if win_prob >= 63 else "★★★☆☆" if win_prob >= 56 else "★★☆☆☆"
    if abs(points) >= 0.1:
        reasons = list(prediction.get("reasons", []))
        reasons.append(f"Self-learning calibration: {points:+.1f} pts")
        prediction["reasons"] = list(dict.fromkeys(reasons))[:6]
    return {"applied": True, "points": round(points, 2), "status": "Active", "trained_games": report.get("graded_games", 0)}

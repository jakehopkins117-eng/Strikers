"""Safe optional ML second-opinion layer.

A trained JSON model can be produced by scripts/train_ml_model.py. Until then,
this module reports an unavailable status and never changes the core pick.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

MODEL_PATH = Path(__file__).resolve().parents[1] / "data" / "ml_model.json"
FEATURES = ["win_pct_gap", "location_gap", "ops_gap", "rpg_gap", "era_gap", "whip_gap", "recent_gap"]


def _number(source: dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        value = source.get(key)
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def feature_vector(payload: dict[str, Any]) -> dict[str, float]:
    away, home = payload["away_team"], payload["home_team"]
    return {
        "win_pct_gap": _number(home, "win_pct") - _number(away, "win_pct"),
        "location_gap": _number(home, "location_win_pct") - _number(away, "location_win_pct"),
        "ops_gap": _number(home, "ops") - _number(away, "ops"),
        "rpg_gap": _number(home, "runs_per_game") - _number(away, "runs_per_game"),
        "era_gap": _number(away, "era") - _number(home, "era"),
        "whip_gap": _number(away, "whip") - _number(home, "whip"),
        "recent_gap": _number(home, "recent_win_pct") - _number(away, "recent_win_pct"),
    }


def model_status() -> dict[str, Any]:
    if not MODEL_PATH.exists():
        return {"available": False, "status": "Collecting data", "model_path": str(MODEL_PATH), "features": FEATURES,
                "message": "No trained model is installed. The core Strikers engine remains active."}
    try:
        model = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
        return {"available": True, "status": "Second opinion active", "model_path": str(MODEL_PATH),
                "features": FEATURES, "trained_rows": model.get("trained_rows", 0), "metrics": model.get("metrics", {})}
    except (OSError, json.JSONDecodeError):
        return {"available": False, "status": "Model file invalid", "model_path": str(MODEL_PATH), "features": FEATURES}


def second_opinion(payload: dict[str, Any]) -> dict[str, Any]:
    status = model_status()
    if not status.get("available"):
        return {**status, "home_probability": None, "away_probability": None, "winner": None, "agreement": None}
    model = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
    vector = feature_vector(payload)
    score = float(model.get("intercept", 0.0))
    for name in FEATURES:
        score += float(model.get("weights", {}).get(name, 0.0)) * vector[name]
    home_probability = 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, score))))
    winner = payload["matchup"]["home"] if home_probability >= 0.5 else payload["matchup"]["away"]
    return {**status, "home_probability": round(home_probability * 100, 2),
            "away_probability": round((1.0 - home_probability) * 100, 2), "winner": winner,
            "agreement": winner == payload["prediction"]["winner"], "features_used": vector}

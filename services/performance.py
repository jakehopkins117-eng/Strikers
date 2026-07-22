"""Prediction grading and performance analytics for Strikers."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Callable


def _probability(item: dict[str, Any]) -> float:
    return max(float(item.get("away_probability", 0)), float(item.get("home_probability", 0)))


def grade_predictions(history: list[dict[str, Any]], schedule_loader: Callable[[str], dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Grade pending predictions against final MLB schedule results."""
    cache: dict[str, list[dict[str, Any]]] = {}
    changed = 0
    for item in history:
        if item.get("result") in {"win", "loss", "push"}:
            continue
        created = str(item.get("created_at", ""))
        game_date = str(item.get("official_date") or "").strip()
        if not game_date:
            try:
                game_date = datetime.fromisoformat(created.replace("Z", "+00:00")).date().isoformat()
            except ValueError:
                continue
        if game_date not in cache:
            try:
                cache[game_date] = schedule_loader(game_date).get("games", [])
            except Exception:
                cache[game_date] = []
        game_pk = item.get("game_pk")
        matchup = next(
            (g for g in cache[game_date] if game_pk is not None and g.get("game_pk") == game_pk),
            None,
        )
        if matchup is None:
            matchup = next(
                (g for g in cache[game_date]
                 if g.get("away", {}).get("name") == item.get("away_team")
                 and g.get("home", {}).get("name") == item.get("home_team")),
                None,
            )
        if not matchup or matchup.get("status", {}).get("abstract") != "Final":
            continue
        away_score = matchup.get("away", {}).get("score")
        home_score = matchup.get("home", {}).get("score")
        if away_score is None or home_score is None or away_score == home_score:
            continue
        actual_winner = item["away_team"] if away_score > home_score else item["home_team"]
        item["actual"] = {"winner": actual_winner, "away_score": away_score, "home_score": home_score}
        item["result"] = "win" if actual_winner == item.get("winner") else "loss"
        item["graded_at"] = datetime.utcnow().isoformat() + "Z"
        changed += 1
    return history, changed


def build_performance(history: list[dict[str, Any]]) -> dict[str, Any]:
    graded = [item for item in history if item.get("result") in {"win", "loss"}]
    wins = sum(item.get("result") == "win" for item in graded)
    losses = len(graded) - wins
    accuracy = round(wins / len(graded) * 100, 1) if graded else 0.0
    # Flat one-unit staking at -110: +0.91 on wins, -1.0 on losses.
    units = round(wins * (100 / 110) - losses, 2)
    roi = round(units / len(graded) * 100, 1) if graded else 0.0

    tiers: dict[str, dict[str, Any]] = defaultdict(lambda: {"predictions": 0, "wins": 0})
    daily: dict[str, dict[str, Any]] = defaultdict(lambda: {"predictions": 0, "wins": 0, "units": 0.0})
    team_stats: dict[str, dict[str, Any]] = defaultdict(lambda: {"predictions": 0, "wins": 0})
    calibration: dict[str, dict[str, Any]] = defaultdict(lambda: {"predictions": 0, "wins": 0, "probability_sum": 0.0})

    for item in graded:
        probability = _probability(item)
        tier = "70%+" if probability >= 70 else "65–69%" if probability >= 65 else "60–64%" if probability >= 60 else "55–59%" if probability >= 55 else "Below 55%"
        won = item.get("result") == "win"
        tiers[tier]["predictions"] += 1; tiers[tier]["wins"] += int(won)
        date_key = str(item.get("created_at", ""))[:10]
        daily[date_key]["predictions"] += 1; daily[date_key]["wins"] += int(won); daily[date_key]["units"] += (100/110 if won else -1)
        team = str(item.get("winner", "Unknown"))
        team_stats[team]["predictions"] += 1; team_stats[team]["wins"] += int(won)
        bucket = f"{int(probability // 5) * 5}-{int(probability // 5) * 5 + 4}%"
        calibration[bucket]["predictions"] += 1; calibration[bucket]["wins"] += int(won); calibration[bucket]["probability_sum"] += probability

    tier_order = ["70%+", "65–69%", "60–64%", "55–59%", "Below 55%"]
    tier_rows = [{"tier": t, **tiers[t], "accuracy": round(tiers[t]["wins"] / tiers[t]["predictions"] * 100, 1) if tiers[t]["predictions"] else 0.0} for t in tier_order]
    trend = []
    cumulative = 0.0
    for d in sorted(daily):
        cumulative += daily[d]["units"]
        trend.append({"date": d, "accuracy": round(daily[d]["wins"] / daily[d]["predictions"] * 100, 1), "predictions": daily[d]["predictions"], "cumulative_units": round(cumulative, 2)})
    teams = sorted(({"team": team, **stats, "accuracy": round(stats["wins"] / stats["predictions"] * 100, 1)} for team, stats in team_stats.items()), key=lambda r: (-r["predictions"], -r["accuracy"]))[:10]
    cal = [{"bucket": bucket, "predictions": row["predictions"], "expected": round(row["probability_sum"] / row["predictions"], 1), "actual": round(row["wins"] / row["predictions"] * 100, 1)} for bucket, row in sorted(calibration.items())]

    streak = 0
    streak_type = None
    for item in history:
        result = item.get("result")
        if result not in {"win", "loss"}: continue
        if streak_type is None: streak_type = result
        if result != streak_type: break
        streak += 1

    return {"summary": {"total_predictions": len(history), "graded_predictions": len(graded), "pending_predictions": len(history)-len(graded), "wins": wins, "losses": losses, "accuracy": accuracy, "units": units, "roi": roi, "current_streak": streak, "streak_type": streak_type}, "confidence_tiers": tier_rows, "trend": trend[-30:], "team_performance": teams, "calibration": cal, "recent": history[:25]}

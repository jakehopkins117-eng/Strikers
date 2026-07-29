"""Statcast cache importer for Strikers Sprint 16.2.

This module downloads season-level Baseball Savant leaderboards through
``pybaseball`` and converts them into the small JSON cache consumed by
``services.statcast_intelligence``. Network work only happens when the user
explicitly runs an import; normal predictions remain fast and resilient.
"""
from __future__ import annotations

import json
import math
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "statcast_players.json"


def _clean(value: Any) -> Any:
    """Convert pandas/numpy values into JSON-safe Python values."""
    if value is None:
        return None
    try:
        if bool(math.isnan(value)):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        try:
            value = value.item()
        except Exception:
            pass
    return value


def _number(row: dict[str, Any], *aliases: str) -> float | None:
    lowered = {str(key).strip().lower(): value for key, value in row.items()}
    for alias in aliases:
        value = _clean(lowered.get(alias.lower()))
        if value in (None, "", "-"):
            continue
        if isinstance(value, str):
            value = value.strip().replace("%", "").replace(",", "")
        try:
            return round(float(value), 4)
        except (TypeError, ValueError):
            continue
    return None


def _text(row: dict[str, Any], *aliases: str) -> str | None:
    lowered = {str(key).strip().lower(): value for key, value in row.items()}
    for alias in aliases:
        value = _clean(lowered.get(alias.lower()))
        if value not in (None, ""):
            return str(value).strip()
    return None


def _player_id(row: dict[str, Any]) -> str | None:
    value = _number(
        row,
        "player_id", "playerid", "id", "mlbam_id", "mlbam", "key_mlbam",
    )
    return str(int(value)) if value is not None else None


def _records(frame: Any) -> list[dict[str, Any]]:
    if frame is None:
        return []
    if hasattr(frame, "to_dict"):
        return list(frame.to_dict(orient="records"))
    if isinstance(frame, list):
        return [dict(row) for row in frame if isinstance(row, dict)]
    raise TypeError("Expected a pandas DataFrame or list of dictionaries")


def _ensure_player(players: dict[str, dict[str, Any]], row: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    player_id = _player_id(row)
    if not player_id:
        return None
    player = players.setdefault(player_id, {})
    name = _text(row, "player_name", "name", "last_name, first_name")
    if name:
        player["name"] = name
    return player_id, player


def merge_hitter_expected(players: dict[str, dict[str, Any]], rows: Iterable[dict[str, Any]]) -> int:
    count = 0
    for row in rows:
        found = _ensure_player(players, row)
        if not found:
            continue
        _, player = found
        hitting = player.setdefault("hitting", {})
        values = {
            "xwoba": _number(row, "est_woba", "estimated_woba", "xwoba", "xwoba_est"),
            "xba": _number(row, "est_ba", "estimated_ba", "xba", "xba_est"),
            "xslg": _number(row, "est_slg", "estimated_slg", "xslg", "xslg_est"),
            "pa": _number(row, "pa", "plate_appearances", "p_attempt"),
        }
        hitting.update({key: value for key, value in values.items() if value is not None})
        count += 1
    return count


def merge_hitter_contact(players: dict[str, dict[str, Any]], rows: Iterable[dict[str, Any]]) -> int:
    count = 0
    for row in rows:
        found = _ensure_player(players, row)
        if not found:
            continue
        _, player = found
        hitting = player.setdefault("hitting", {})
        values = {
            "barrel_pct": _number(row, "brl_percent", "barrel_batted_rate", "barrel_pct", "barrels_per_bbe_percent"),
            "hard_hit_pct": _number(row, "hard_hit_percent", "hardhit_percent", "hard_hit_pct", "hardhit%"),
            "avg_exit_velocity": _number(row, "avg_hit_speed", "avg_exit_velocity", "exit_velocity_avg", "ev"),
            "max_exit_velocity": _number(row, "max_hit_speed", "max_exit_velocity", "max_ev"),
            "sweet_spot_pct": _number(row, "anglesweetspotpercent", "sweet_spot_percent", "sweet_spot_pct"),
            "bbe": _number(row, "bbe", "batted_ball_events", "attempts"),
        }
        hitting.update({key: value for key, value in values.items() if value is not None})
        count += 1
    return count


def merge_pitcher_expected(players: dict[str, dict[str, Any]], rows: Iterable[dict[str, Any]]) -> int:
    count = 0
    for row in rows:
        found = _ensure_player(players, row)
        if not found:
            continue
        _, player = found
        pitching = player.setdefault("pitching", {})
        values = {
            "xera": _number(row, "est_era", "estimated_era", "xera", "xera_est"),
            "xwoba_allowed": _number(row, "est_woba", "estimated_woba", "xwoba", "xwoba_est"),
            "xba_allowed": _number(row, "est_ba", "estimated_ba", "xba", "xba_est"),
            "xslg_allowed": _number(row, "est_slg", "estimated_slg", "xslg", "xslg_est"),
            "pa_against": _number(row, "pa", "plate_appearances", "p_attempt"),
        }
        pitching.update({key: value for key, value in values.items() if value is not None})
        count += 1
    return count


def merge_pitcher_contact(players: dict[str, dict[str, Any]], rows: Iterable[dict[str, Any]]) -> int:
    count = 0
    for row in rows:
        found = _ensure_player(players, row)
        if not found:
            continue
        _, player = found
        pitching = player.setdefault("pitching", {})
        values = {
            "barrel_pct_allowed": _number(row, "brl_percent", "barrel_batted_rate", "barrel_pct", "barrels_per_bbe_percent"),
            "hard_hit_pct_allowed": _number(row, "hard_hit_percent", "hardhit_percent", "hard_hit_pct", "hardhit%"),
            "avg_exit_velocity_allowed": _number(row, "avg_hit_speed", "avg_exit_velocity", "exit_velocity_avg", "ev"),
            "max_exit_velocity_allowed": _number(row, "max_hit_speed", "max_exit_velocity", "max_ev"),
            "sweet_spot_pct_allowed": _number(row, "anglesweetspotpercent", "sweet_spot_percent", "sweet_spot_pct"),
            "bbe_against": _number(row, "bbe", "batted_ball_events", "attempts"),
        }
        pitching.update({key: value for key, value in values.items() if value is not None})
        count += 1
    return count


def build_cache_from_frames(
    *, season: int, hitter_expected: Any, hitter_contact: Any,
    pitcher_expected: Any, pitcher_contact: Any,
    min_pa: int, min_bbe: int,
) -> dict[str, Any]:
    players: dict[str, dict[str, Any]] = {}
    source_rows = {
        "hitter_expected": merge_hitter_expected(players, _records(hitter_expected)),
        "hitter_contact": merge_hitter_contact(players, _records(hitter_contact)),
        "pitcher_expected": merge_pitcher_expected(players, _records(pitcher_expected)),
        "pitcher_contact": merge_pitcher_contact(players, _records(pitcher_contact)),
    }
    return {
        "version": "16.2",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "season": season,
        "source": "Baseball Savant via pybaseball",
        "settings": {"min_pa": min_pa, "min_bbe": min_bbe},
        "source_rows": source_rows,
        "players": players,
    }


def write_cache(payload: dict[str, Any], path: Path = DATA_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        backup = path.with_suffix(".previous.json")
        shutil.copy2(path, backup)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(path)
    return path


def import_statcast_cache(season: int, min_pa: int = 25, min_bbe: int = 15) -> dict[str, Any]:
    if season < 2015 or season > datetime.now().year:
        raise ValueError("season must be between 2015 and the current year")
    if min_pa < 1 or min_bbe < 1:
        raise ValueError("minimum thresholds must be positive")

    try:
        from pybaseball import (
            statcast_batter_expected_stats,
            statcast_batter_exitvelo_barrels,
            statcast_pitcher_expected_stats,
            statcast_pitcher_exitvelo_barrels,
        )
    except ImportError as exc:
        raise RuntimeError(
            "pybaseball is not installed. Run: python -m pip install -r requirements.txt"
        ) from exc

    hitter_expected = statcast_batter_expected_stats(season, minPA=min_pa)
    hitter_contact = statcast_batter_exitvelo_barrels(season, minBBE=min_bbe)
    pitcher_expected = statcast_pitcher_expected_stats(season, minPA=min_pa)
    pitcher_contact = statcast_pitcher_exitvelo_barrels(season, minBBE=min_bbe)

    payload = build_cache_from_frames(
        season=season,
        hitter_expected=hitter_expected,
        hitter_contact=hitter_contact,
        pitcher_expected=pitcher_expected,
        pitcher_contact=pitcher_contact,
        min_pa=min_pa,
        min_bbe=min_bbe,
    )
    write_cache(payload)
    players = payload["players"]
    return {
        "success": True,
        "version": payload["version"],
        "season": season,
        "updated_at": payload["updated_at"],
        "player_count": len(players),
        "hitter_rows": sum(1 for player in players.values() if player.get("hitting")),
        "pitcher_rows": sum(1 for player in players.values() if player.get("pitching")),
        "source_rows": payload["source_rows"],
        "data_path": str(DATA_PATH),
        "mode": "observe-only",
        "message": "Statcast cache imported. Predictions still remain observe-only in Sprint 16.2.",
    }

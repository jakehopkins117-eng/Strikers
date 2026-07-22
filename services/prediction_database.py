"""SQLite persistence for Strikers predictions and model datasets."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "strikers.db"


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=15)
    connection.row_factory = sqlite3.Row
    return connection


def _date_from_timestamp(value: str | None) -> str | None:
    if not value:
        return None
    return str(value)[:10] or None


def _deduplicate_predictions(db: sqlite3.Connection) -> int:
    """Collapse repeated checks of the same game to one canonical record.

    New records use MLB game_pk. Legacy records fall back to official date plus
    away/home matchup. The newest prediction is kept, while any existing grade
    from the duplicate group is preserved.
    """
    rows = db.execute("SELECT * FROM predictions ORDER BY created_at DESC").fetchall()
    groups: dict[tuple[Any, ...], list[sqlite3.Row]] = {}
    for row in rows:
        official_date = row["official_date"] or _date_from_timestamp(row["created_at"])
        if row["game_pk"] is not None:
            key = ("game_pk", int(row["game_pk"]))
        else:
            key = ("matchup", official_date, row["away_team"], row["home_team"])
        groups.setdefault(key, []).append(row)

    removed = 0
    for items in groups.values():
        if len(items) <= 1:
            row = items[0]
            if not row["official_date"]:
                db.execute(
                    "UPDATE predictions SET official_date=? WHERE id=?",
                    (_date_from_timestamp(row["created_at"]), row["id"]),
                )
            continue

        keep = items[0]  # query is newest first
        graded = next((item for item in items if item["result"] in {"win", "loss", "push"}), None)
        official_date = keep["official_date"] or _date_from_timestamp(keep["created_at"])
        game_pk = keep["game_pk"] or next((item["game_pk"] for item in items if item["game_pk"] is not None), None)
        db.execute(
            """UPDATE predictions
               SET game_pk=?, official_date=?, result=?, actual_winner=?,
                   actual_away_score=?, actual_home_score=?
               WHERE id=?""",
            (
                game_pk,
                official_date,
                graded["result"] if graded else keep["result"],
                graded["actual_winner"] if graded else keep["actual_winner"],
                graded["actual_away_score"] if graded else keep["actual_away_score"],
                graded["actual_home_score"] if graded else keep["actual_home_score"],
                keep["id"],
            ),
        )
        duplicate_ids = [item["id"] for item in items[1:]]
        db.executemany("DELETE FROM predictions WHERE id=?", [(record_id,) for record_id in duplicate_ids])
        removed += len(duplicate_ids)
    return removed


def initialize_database() -> None:
    with connect() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS predictions (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                away_team TEXT NOT NULL,
                home_team TEXT NOT NULL,
                predicted_winner TEXT NOT NULL,
                away_probability REAL NOT NULL,
                home_probability REAL NOT NULL,
                confidence TEXT,
                confidence_stars TEXT,
                projected_away REAL,
                projected_home REAL,
                model_version TEXT,
                game_pk INTEGER,
                official_date TEXT,
                actual_winner TEXT,
                actual_away_score INTEGER,
                actual_home_score INTEGER,
                result TEXT,
                away_odds INTEGER,
                home_odds INTEGER,
                selected_value_team TEXT,
                selected_value_ev REAL,
                feature_json TEXT NOT NULL DEFAULT '{}',
                payload_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_predictions_created_at ON predictions(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_predictions_matchup ON predictions(away_team, home_team);
            CREATE INDEX IF NOT EXISTS idx_predictions_result ON predictions(result);
            """
        )
        _deduplicate_predictions(db)
        db.executescript(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_predictions_game_pk
                ON predictions(game_pk) WHERE game_pk IS NOT NULL;
            CREATE UNIQUE INDEX IF NOT EXISTS uq_predictions_matchup_date
                ON predictions(official_date, away_team, home_team)
                WHERE game_pk IS NULL AND official_date IS NOT NULL;
            """
        )


def _find_existing_id(
    db: sqlite3.Connection,
    *,
    game_pk: int | None,
    official_date: str | None,
    away_team: str,
    home_team: str,
) -> str | None:
    if game_pk is not None:
        row = db.execute("SELECT id FROM predictions WHERE game_pk=?", (game_pk,)).fetchone()
        if row:
            return str(row["id"])
    if official_date:
        row = db.execute(
            """SELECT id FROM predictions
               WHERE official_date=? AND away_team=? AND home_team=?
               ORDER BY created_at DESC LIMIT 1""",
            (official_date, away_team, home_team),
        ).fetchone()
        if row:
            return str(row["id"])
    return None


def save_prediction(payload: dict[str, Any], betting: dict[str, Any] | None = None, *, record_id: str | None = None, created_at: str | None = None) -> str:
    initialize_database()
    prediction = payload["prediction"]
    intelligence = payload.get("intelligence", {})
    created_at = created_at or datetime.now(timezone.utc).isoformat()
    game_pk_raw = payload.get("game_pk")
    game_pk = int(game_pk_raw) if game_pk_raw not in (None, "") else None
    official_date = payload.get("official_date") or (_date_from_timestamp(created_at) if game_pk is not None else None)
    away_team = payload["matchup"]["away"]
    home_team = payload["matchup"]["home"]
    best_value = (betting or {}).get("best_value") or {}
    feature_payload = {
        "away_team": payload.get("away_team", {}),
        "home_team": payload.get("home_team", {}),
        "away_pitcher": payload.get("away_pitcher", {}),
        "home_pitcher": payload.get("home_pitcher", {}),
        "factors": intelligence.get("factors", []),
    }
    values = (
        created_at, away_team, home_team, prediction["winner"],
        float(prediction["away_probability"]), float(prediction["home_probability"]),
        prediction.get("confidence"), prediction.get("confidence_stars"),
        prediction.get("away_score"), prediction.get("home_score"),
        intelligence.get("model_version"), game_pk, official_date,
        next((s.get("odds") for s in (betting or {}).get("sides", []) if s.get("team") == away_team), None),
        next((s.get("odds") for s in (betting or {}).get("sides", []) if s.get("team") == home_team), None),
        best_value.get("team"), best_value.get("expected_value"),
        json.dumps(feature_payload), json.dumps(payload),
    )
    with connect() as db:
        existing_id = _find_existing_id(
            db, game_pk=game_pk, official_date=official_date,
            away_team=away_team, home_team=home_team,
        )
        if existing_id:
            db.execute(
                """UPDATE predictions SET
                   created_at=?, away_team=?, home_team=?, predicted_winner=?,
                   away_probability=?, home_probability=?, confidence=?, confidence_stars=?,
                   projected_away=?, projected_home=?, model_version=?, game_pk=?, official_date=?,
                   away_odds=?, home_odds=?, selected_value_team=?, selected_value_ev=?,
                   feature_json=?, payload_json=?
                   WHERE id=?""",
                values + (existing_id,),
            )
            return existing_id

        record_id = record_id or str(uuid4())
        db.execute(
            """INSERT INTO predictions (
                id, created_at, away_team, home_team, predicted_winner,
                away_probability, home_probability, confidence, confidence_stars,
                projected_away, projected_home, model_version, game_pk, official_date,
                away_odds, home_odds, selected_value_team, selected_value_ev,
                feature_json, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (record_id,) + values,
        )
    return record_id


def list_predictions(
    *, limit: int = 100, team: str | None = None,
    confidence: str | None = None, result: str | None = None,
) -> list[dict[str, Any]]:
    initialize_database()
    clauses: list[str] = []
    params: list[Any] = []
    if team:
        clauses.append("(away_team LIKE ? OR home_team LIKE ?)")
        params.extend([f"%{team}%", f"%{team}%"])
    if confidence:
        clauses.append("confidence = ?")
        params.append(confidence)
    if result:
        clauses.append("result = ?")
        params.append(result)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)
    query = f"SELECT * FROM predictions {where} ORDER BY created_at DESC LIMIT ?"
    with connect() as db:
        rows = db.execute(query, params).fetchall()
    return [_row_payload(row) for row in rows]


def _row_payload(row: sqlite3.Row) -> dict[str, Any]:
    payload = json.loads(row["payload_json"])
    return {
        "id": row["id"], "created_at": row["created_at"],
        "game_pk": row["game_pk"], "official_date": row["official_date"],
        "away_team": row["away_team"], "home_team": row["home_team"],
        "winner": row["predicted_winner"],
        "away_probability": row["away_probability"],
        "home_probability": row["home_probability"],
        "confidence": row["confidence"], "confidence_stars": row["confidence_stars"],
        "projected_score": {"away": row["projected_away"], "home": row["projected_home"]},
        "reasons": payload.get("prediction", {}).get("reasons", []),
        "away_logo": payload.get("away_team", {}).get("logo"),
        "home_logo": payload.get("home_team", {}).get("logo"),
        "result": row["result"],
        "actual": None if row["actual_winner"] is None else {
            "winner": row["actual_winner"], "away_score": row["actual_away_score"], "home_score": row["actual_home_score"]
        },
        "model_version": row["model_version"],
        "betting": {"away_odds": row["away_odds"], "home_odds": row["home_odds"], "value_team": row["selected_value_team"], "value_ev": row["selected_value_ev"]},
    }


def update_grades(history: list[dict[str, Any]]) -> int:
    """Persist grading fields calculated by services.performance.grade_predictions."""
    initialize_database()
    changed = 0
    with connect() as db:
        for item in history:
            if item.get("result") not in {"win", "loss", "push"}:
                continue
            actual = item.get("actual") or {}
            cursor = db.execute(
                """UPDATE predictions SET result=?, actual_winner=?,
                   actual_away_score=?, actual_home_score=? WHERE id=?""",
                (item.get("result"), actual.get("winner"), actual.get("away_score"), actual.get("home_score"), item.get("id")),
            )
            changed += cursor.rowcount
    return changed


def summary() -> dict[str, Any]:
    initialize_database()
    with connect() as db:
        row = db.execute(
            """SELECT COUNT(*) total,
            SUM(CASE WHEN result IS NOT NULL THEN 1 ELSE 0 END) graded,
            SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) wins,
            AVG(CASE WHEN result = 'win' THEN 1.0 WHEN result = 'loss' THEN 0.0 END) accuracy
            FROM predictions"""
        ).fetchone()
        recent = db.execute("SELECT * FROM predictions ORDER BY created_at DESC LIMIT 5").fetchall()
    total = int(row["total"] or 0); graded = int(row["graded"] or 0); wins = int(row["wins"] or 0)
    return {"total": total, "graded": graded, "pending": total - graded, "wins": wins,
            "losses": max(graded - wins, 0), "accuracy": round(float(row["accuracy"] or 0) * 100, 1),
            "recent": [_row_payload(item) for item in recent]}


def clear_predictions() -> None:
    initialize_database()
    with connect() as db:
        db.execute("DELETE FROM predictions")


def import_legacy_history(history: list[dict[str, Any]]) -> int:
    """One-time import of legacy JSON history, deduplicated by game/date matchup."""
    initialize_database()
    changed = 0
    for item in history:
        created_at = item.get("created_at") or datetime.now(timezone.utc).isoformat()
        payload = {
            "game_pk": item.get("game_pk"),
            "official_date": item.get("official_date") or _date_from_timestamp(created_at),
            "matchup": {"away": item.get("away_team"), "home": item.get("home_team")},
            "prediction": {"winner": item.get("winner"), "away_probability": item.get("away_probability", 0), "home_probability": item.get("home_probability", 0), "confidence": item.get("confidence"), "confidence_stars": item.get("confidence_stars"), "away_score": (item.get("projected_score") or {}).get("away"), "home_score": (item.get("projected_score") or {}).get("home"), "reasons": item.get("reasons", [])},
            "away_team": {"logo": item.get("away_logo")}, "home_team": {"logo": item.get("home_logo")},
            "away_pitcher": {}, "home_pitcher": {}, "intelligence": {"model_version": item.get("model_version", "legacy")},
        }
        record_id = save_prediction(payload, record_id=str(item.get("id") or uuid4()), created_at=created_at)
        actual = item.get("actual") or {}
        if item.get("result") in {"win", "loss", "push"}:
            with connect() as db:
                db.execute(
                    "UPDATE predictions SET result=?, actual_winner=?, actual_away_score=?, actual_home_score=? WHERE id=?",
                    (item.get("result"), actual.get("winner"), actual.get("away_score"), actual.get("home_score"), record_id),
                )
        changed += 1
    initialize_database()
    return changed

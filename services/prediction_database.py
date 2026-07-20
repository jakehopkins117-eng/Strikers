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


def save_prediction(payload: dict[str, Any], betting: dict[str, Any] | None = None, *, record_id: str | None = None, created_at: str | None = None) -> str:
    initialize_database()
    prediction = payload["prediction"]
    intelligence = payload.get("intelligence", {})
    record_id = record_id or str(uuid4())
    created_at = created_at or datetime.now(timezone.utc).isoformat()
    best_value = (betting or {}).get("best_value") or {}
    feature_payload = {
        "away_team": payload.get("away_team", {}),
        "home_team": payload.get("home_team", {}),
        "away_pitcher": payload.get("away_pitcher", {}),
        "home_pitcher": payload.get("home_pitcher", {}),
        "factors": intelligence.get("factors", []),
    }
    with connect() as db:
        db.execute(
            """
            INSERT INTO predictions (
                id, created_at, away_team, home_team, predicted_winner,
                away_probability, home_probability, confidence, confidence_stars,
                projected_away, projected_home, model_version,
                away_odds, home_odds, selected_value_team, selected_value_ev,
                feature_json, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record_id,
                created_at,
                payload["matchup"]["away"], payload["matchup"]["home"],
                prediction["winner"], float(prediction["away_probability"]),
                float(prediction["home_probability"]), prediction.get("confidence"),
                prediction.get("confidence_stars"), prediction.get("away_score"),
                prediction.get("home_score"), intelligence.get("model_version"),
                next((s.get("odds") for s in (betting or {}).get("sides", []) if s.get("team") == payload["matchup"]["away"]), None),
                next((s.get("odds") for s in (betting or {}).get("sides", []) if s.get("team") == payload["matchup"]["home"]), None),
                best_value.get("team"), best_value.get("expected_value"),
                json.dumps(feature_payload), json.dumps(payload),
            ),
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
    """Import or update legacy JSON history without deleting richer SQLite rows."""
    initialize_database()
    changed = 0
    with connect() as db:
        for item in history:
            record_id = str(item.get("id") or uuid4())
            existing = db.execute("SELECT id FROM predictions WHERE id = ?", (record_id,)).fetchone()
            actual = item.get("actual") or {}
            if existing:
                db.execute(
                    "UPDATE predictions SET result=?, actual_winner=?, actual_away_score=?, actual_home_score=? WHERE id=?",
                    (item.get("result"), actual.get("winner"), actual.get("away_score"), actual.get("home_score"), record_id),
                )
                changed += 1
                continue
            payload = {
                "matchup": {"away": item.get("away_team"), "home": item.get("home_team")},
                "prediction": {"winner": item.get("winner"), "away_probability": item.get("away_probability", 0), "home_probability": item.get("home_probability", 0), "confidence": item.get("confidence"), "confidence_stars": item.get("confidence_stars"), "away_score": (item.get("projected_score") or {}).get("away"), "home_score": (item.get("projected_score") or {}).get("home"), "reasons": item.get("reasons", [])},
                "away_team": {"logo": item.get("away_logo")}, "home_team": {"logo": item.get("home_logo")},
                "away_pitcher": {}, "home_pitcher": {}, "intelligence": {"model_version": item.get("model_version", "legacy")},
            }
            db.execute(
                """INSERT INTO predictions (id,created_at,away_team,home_team,predicted_winner,away_probability,home_probability,confidence,confidence_stars,projected_away,projected_home,model_version,actual_winner,actual_away_score,actual_home_score,result,feature_json,payload_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (record_id, item.get("created_at") or datetime.now(timezone.utc).isoformat(), item.get("away_team"), item.get("home_team"), item.get("winner"), float(item.get("away_probability",0)), float(item.get("home_probability",0)), item.get("confidence"), item.get("confidence_stars"), (item.get("projected_score") or {}).get("away"), (item.get("projected_score") or {}).get("home"), item.get("model_version","legacy"), actual.get("winner"), actual.get("away_score"), actual.get("home_score"), item.get("result"), "{}", json.dumps(payload)),
            )
            changed += 1
    return changed

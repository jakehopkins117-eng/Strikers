"""Train a small logistic-regression second-opinion model using completed SQLite rows.
Run from project root: python scripts/train_ml_model.py
"""
from __future__ import annotations
import json, math, sqlite3, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.ml_foundation import FEATURES  # noqa: E402

DB = ROOT / "data" / "strikers.db"; OUT = ROOT / "data" / "ml_model.json"

def sigmoid(x: float) -> float: return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, x))))

def main() -> None:
    if not DB.exists(): raise SystemExit("No database found. Generate and grade predictions first.")
    with sqlite3.connect(DB) as db:
        rows = db.execute("SELECT feature_json, home_team, actual_winner FROM predictions WHERE actual_winner IS NOT NULL").fetchall()
    if len(rows) < 30: raise SystemExit(f"Need at least 30 completed predictions; found {len(rows)}.")
    samples=[]
    for raw, home, actual in rows:
        payload=json.loads(raw); away=payload.get("away_team",{}); h=payload.get("home_team",{})
        def n(src,k):
            try:return float(src.get(k) or 0)
            except:return 0.0
        x={"win_pct_gap":n(h,"win_pct")-n(away,"win_pct"),"location_gap":n(h,"location_win_pct")-n(away,"location_win_pct"),"ops_gap":n(h,"ops")-n(away,"ops"),"rpg_gap":n(h,"runs_per_game")-n(away,"runs_per_game"),"era_gap":n(away,"era")-n(h,"era"),"whip_gap":n(away,"whip")-n(h,"whip"),"recent_gap":n(h,"recent_win_pct")-n(away,"recent_win_pct")}
        samples.append((x,1.0 if actual==home else 0.0))
    weights={name:0.0 for name in FEATURES}; intercept=0.0; rate=0.08
    for _ in range(2500):
        gi=0.0; gw={name:0.0 for name in FEATURES}
        for x,y in samples:
            p=sigmoid(intercept+sum(weights[n]*x[n] for n in FEATURES)); e=p-y; gi+=e
            for n in FEATURES: gw[n]+=e*x[n]
        scale=1.0/len(samples); intercept-=rate*gi*scale
        for n in FEATURES: weights[n]-=rate*gw[n]*scale
    correct=0
    for x,y in samples:
        p=sigmoid(intercept+sum(weights[n]*x[n] for n in FEATURES)); correct += int((p>=.5)==bool(y))
    OUT.write_text(json.dumps({"version":"1.0","trained_rows":len(samples),"intercept":intercept,"weights":weights,"metrics":{"training_accuracy":round(correct/len(samples)*100,1)}},indent=2),encoding="utf-8")
    print(f"Saved {OUT} using {len(samples)} rows.")
if __name__ == "__main__": main()

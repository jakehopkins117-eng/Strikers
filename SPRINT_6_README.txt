STRIKERS SPRINT 6 — PLAYER PROPS

Replace your project files with this package while on sprint-6-prop-bets.

Adds:
- Player Props navigation page
- Pitcher strikeouts, outs, earned-runs projections
- Batter hits, total bases, home runs, RBI projections
- Search and market filters
- Manual sportsbook line and American-odds analyzer
- Fair odds, estimated probability, edge, and EV

Restart backend:
cd "C:\Users\Jake Hopkins\Desktop\Strikers"
python -m uvicorn web_api:app --reload

Restart frontend:
cd "C:\Users\Jake Hopkins\Desktop\Strikers\frontend"
"C:\Program Files\nodejs\npm.cmd" run dev

Open http://localhost:5173 and choose Player Props.

Note: Default lines are model reference lines, not live sportsbook data.

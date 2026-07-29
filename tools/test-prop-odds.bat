@echo off
cd /d "%~dp0.."
echo Testing Sprint 19.1 live player props...
python -c "from services.prop_odds import prop_odds_status; import json; print(json.dumps(prop_odds_status(), indent=2))"
echo.
echo Start the backend, then open:
echo http://127.0.0.1:8000/player-props/live/status
echo http://127.0.0.1:8000/player-props/live
pause

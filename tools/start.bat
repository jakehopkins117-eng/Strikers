@echo off
setlocal
cd /d "%~dp0\.."
start "Strikers Backend" cmd /k python -m uvicorn web_api:app --reload
start "Strikers Frontend" cmd /k "cd /d frontend && npm run dev"
timeout /t 4 /nobreak >nul
start "" http://localhost:5173

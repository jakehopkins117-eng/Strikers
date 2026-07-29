$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Frontend = Join-Path $Root "frontend"

Write-Host "Starting Strikers..." -ForegroundColor Cyan

$python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }

Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$Root'; & '$python' -m uvicorn web_api:app --reload"
Start-Sleep -Seconds 2
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$Frontend'; npm run dev"
Start-Sleep -Seconds 3
Start-Process "http://localhost:5173"
Write-Host "Backend and frontend launch commands were sent." -ForegroundColor Green

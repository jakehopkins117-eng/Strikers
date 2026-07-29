$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }

Write-Host "Checking Python compilation..." -ForegroundColor Cyan
& $python -m compileall -q api services utils web_api.py
Write-Host "Checking backend imports..." -ForegroundColor Cyan
& $python -c "import web_api; from services.statcast_intelligence import statcast_status; print(statcast_status())"
Write-Host "Building frontend..." -ForegroundColor Cyan
Set-Location (Join-Path $Root "frontend")
npm run build
Write-Host "All tests passed." -ForegroundColor Green

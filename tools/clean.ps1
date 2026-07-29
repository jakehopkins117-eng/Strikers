$Root = Split-Path -Parent $PSScriptRoot
Write-Host "Removing caches..." -ForegroundColor Cyan
Get-ChildItem $Root -Recurse -Force -Directory | Where-Object { $_.Name -in @("__pycache__", ".pytest_cache") } | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem $Root -Recurse -Force -File -Filter "*.pyc" | Remove-Item -Force -ErrorAction SilentlyContinue
Write-Host "Caches removed." -ForegroundColor Green

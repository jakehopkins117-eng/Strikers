$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Stamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$Destination = Join-Path ([Environment]::GetFolderPath("Desktop")) "Strikers_$Stamp.zip"
$Temp = Join-Path $env:TEMP "StrikersBackup_$Stamp"

Write-Host "Creating clean Strikers backup..." -ForegroundColor Cyan
New-Item -ItemType Directory -Path $Temp -Force | Out-Null

$exclude = @(".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", "dist", "build")
Get-ChildItem -LiteralPath $Root -Force | Where-Object { $exclude -notcontains $_.Name } | ForEach-Object {
    Copy-Item $_.FullName -Destination $Temp -Recurse -Force
}
Get-ChildItem $Temp -Recurse -Force | Where-Object { $_.Name -eq "__pycache__" -or $_.Extension -eq ".pyc" } | Remove-Item -Recurse -Force
Compress-Archive -Path (Join-Path $Temp "*") -DestinationPath $Destination -Force
Remove-Item $Temp -Recurse -Force
Write-Host "Backup created:" -ForegroundColor Green
Write-Host $Destination

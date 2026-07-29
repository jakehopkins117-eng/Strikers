$Root = Split-Path -Parent $PSScriptRoot
$checks = @()
function Add-Check($Name, $Ok, $Detail) {
    $script:checks += [PSCustomObject]@{ Check=$Name; Status=$(if($Ok){"PASS"}else{"FAIL"}); Detail=$Detail }
}

$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
Add-Check "Python" ($null -ne $pythonCmd) $(if($pythonCmd){python --version}else{"Not found"})
$nodeCmd = Get-Command node -ErrorAction SilentlyContinue
Add-Check "Node" ($null -ne $nodeCmd) $(if($nodeCmd){node --version}else{"Not found"})
$npmCmd = Get-Command npm -ErrorAction SilentlyContinue
Add-Check "npm" ($null -ne $npmCmd) $(if($npmCmd){npm --version}else{"Not found"})
Add-Check "web_api.py" (Test-Path (Join-Path $Root "web_api.py")) "Backend entry point"
Add-Check "Frontend" (Test-Path (Join-Path $Root "frontend\package.json")) "frontend/package.json"
Add-Check ".env" (Test-Path (Join-Path $Root ".env")) "Local environment file"
if ($pythonCmd) {
    python -c "import fastapi, uvicorn, requests, pydantic, dotenv" 2>$null
    Add-Check "Python packages" ($LASTEXITCODE -eq 0) "fastapi, uvicorn, requests, pydantic, dotenv"
}
$checks | Format-Table -AutoSize
if ($checks.Status -contains "FAIL") { exit 1 }

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
& (Join-Path $root '.venv\Scripts\python.exe') scripts/demo_preflight.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$env:AGENT_PROVIDER = 'mock'
$env:QWEN_MOCK = '1'
$env:VITE_DEMO_MODE = 'true'
$backend = Start-Process -FilePath (Join-Path $root '.venv\Scripts\python.exe') -ArgumentList '-m','uvicorn','app.api:app','--host','127.0.0.1','--port','9000' -WorkingDirectory $root -PassThru
$frontend = Start-Process -FilePath 'C:\Program Files\nodejs\npm.cmd' -ArgumentList 'run','dev','--','--host','127.0.0.1','--port','5173' -WorkingDirectory (Join-Path $root 'frontend') -PassThru
Write-Host "Demo backend PID $($backend.Id): http://127.0.0.1:9000/health"
Write-Host "Demo frontend PID $($frontend.Id): http://127.0.0.1:5173/workbench"
Write-Host 'Mode: DEMO CACHED MODE (mock/offline fallback; no live Qwen request).'

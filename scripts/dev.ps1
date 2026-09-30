$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$backend = Start-Process -FilePath (Join-Path $root '.venv\Scripts\python.exe') -ArgumentList '-m','uvicorn','app.api:app','--reload','--host','127.0.0.1','--port','8000' -WorkingDirectory $root -PassThru
$frontend = Start-Process -FilePath 'C:\Program Files\nodejs\npm.cmd' -ArgumentList 'run','dev','--','--host','127.0.0.1','--port','5173' -WorkingDirectory (Join-Path $root 'frontend') -PassThru
Write-Host "Backend PID $($backend.Id): http://127.0.0.1:8000"
Write-Host "Frontend PID $($frontend.Id): http://127.0.0.1:5173/workbench"
Write-Host 'Stop both processes when finished.'

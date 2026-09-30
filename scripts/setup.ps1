$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
if (-not (Test-Path '.venv\Scripts\python.exe')) { python -m venv .venv }
& '.venv\Scripts\python.exe' -m pip install -r requirements.txt
& 'C:\Program Files\nodejs\npm.cmd' --prefix frontend install
& '.venv\Scripts\python.exe' scripts/import_excel_to_sqlite.py --db data/beauty_cs_agent.sqlite3
Write-Host 'Setup complete. Start backend and frontend with scripts/dev.ps1.'

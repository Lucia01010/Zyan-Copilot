@echo off
rem Zhiyan service process (spawned minimized by start_zhiyan.cmd)
cd /d "%~dp0.."
if not exist logs mkdir logs
set "AGENT_PROVIDER=mock"
set "QWEN_MOCK=1"
set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" -m uvicorn app.api:app --host 127.0.0.1 --port 8000 > logs\zhiyan_service.log 2>&1

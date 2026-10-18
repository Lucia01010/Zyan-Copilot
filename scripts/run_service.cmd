@echo off
rem Zhiyan service process (spawned minimized by start_zhiyan.cmd)
cd /d "%~dp0\.."
if not exist logs mkdir logs
rem 运行模式由 .env 决定（AGENT_PROVIDER=qwen 为实时大模型，mock 为离线演示）；
rem 此处不再注入默认值，避免覆盖 .env 配置。未配置 .env 时 Python 侧自动回退 mock。
set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" -m uvicorn app.api:app --host 127.0.0.1 --port 9000 > logs\zhiyan_service.log 2>&1

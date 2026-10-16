@echo off
setlocal
cd /d "%~dp0\.."

rem ============================================================
rem Zhiyan AI one-click launcher (single process serves FE + BE)
rem Opens http://localhost:9000/workbench when ready.
rem Service log: logs\zhiyan_service.log  (shown here if start fails)
rem ============================================================

if not exist logs mkdir logs

netstat -ano -p tcp | findstr /C:"127.0.0.1:9000" | findstr "LISTENING" >nul 2>nul
if %errorlevel%==0 goto open_browser

echo [Zhiyan] Starting service, first start takes a few seconds ...
start "Zhiyan AI (port 9000)" /MIN "%~dp0run_service.cmd"

set /a tries=0
:wait_loop
set /a tries+=1
ping -n 2 127.0.0.1 >nul
netstat -ano -p tcp | findstr /C:"127.0.0.1:9000" | findstr "LISTENING" >nul 2>nul
if %errorlevel%==0 goto open_browser
if %tries% geq 30 (
  echo [Zhiyan] Service failed to start. Error log below:
  echo ----------------------------------------------------
  type logs\zhiyan_service.log
  echo ----------------------------------------------------
  echo Common causes: port 9000 occupied / .venv missing / deps not installed.
  echo Full log: logs\zhiyan_service.log
  pause
  exit /b 1
)
goto wait_loop

:open_browser
start "" "http://localhost:9000/workbench"
echo [Zhiyan] Opened http://localhost:9000/workbench in your browser.
echo [Zhiyan] Service log: logs\zhiyan_service.log
echo [Zhiyan] Close the minimized "Zhiyan AI" window to stop the service.
timeout /t 3 >nul
endlocal

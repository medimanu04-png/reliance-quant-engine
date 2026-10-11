@echo off
REM ==============================================================================
REM Manoj Quant Engine - 09:00 AM IST Pre-Market System Health Check & Telemetry
REM Dispatches executive trading calendar & Groww broker readiness to Telegram
REM ==============================================================================

cd /d "%~dp0"

IF EXIST ".venv\Scripts\python.exe" (
    SET "PY_BIN=.venv\Scripts\python.exe"
) ELSE (
    SET "PY_BIN=python"
)

echo [%DATE% %TIME%] Launching 09:00 AM Pre-Market Health Diagnostics...
"%PY_BIN%" pre_market_health_check.py --force --telegram
echo [%DATE% %TIME%] Pre-Market Health Diagnostics Completed with exit code %ERRORLEVEL%.
exit /b %ERRORLEVEL%

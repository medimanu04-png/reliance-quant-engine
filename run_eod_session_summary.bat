@echo off
REM ==============================================================================
REM Manoj Quant Engine - 03:30 PM IST End-of-Day Performance Debrief & Database Backup
REM Compiles daily trade metrics, takes JSON backup, and dispatches to Telegram
REM ==============================================================================

cd /d "%~dp0"

IF EXIST ".venv\Scripts\python.exe" (
    SET "PY_BIN=.venv\Scripts\python.exe"
) ELSE (
    SET "PY_BIN=python"
)

echo [%DATE% %TIME%] Launching 03:30 PM EOD Audit and Database Backup...
"%PY_BIN%" eod_session_summary.py --force --telegram
echo [%DATE% %TIME%] EOD Session Audit Completed with exit code %ERRORLEVEL%.
exit /b %ERRORLEVEL%

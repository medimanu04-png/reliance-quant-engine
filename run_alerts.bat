@echo off
cd /d "%~dp0"
title Quant Engine - Background Alert Daemon
color 0A
echo =======================================================================
echo   NIFTY & SENSEX F^&O QUANTITATIVE ENGINE — 24/7 TELEGRAM ALERT DAEMON
echo =======================================================================
echo   * Operates completely independently of Streamlit and web browsers.
echo   * Active Trading Window: 09:15 AM to 03:30 PM IST (Mon-Fri).
echo   * Automatically tracks Dual ATM options, targets, and stop losses.
echo   * Dispatches instant zero-delay alerts directly to Telegram.
echo =======================================================================
echo.

if not exist ".\.venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found in .venv!
    echo Please ensure Python environment is installed.
    pause
    exit /b 1
)

call ".\.venv\Scripts\activate.bat"

echo Starting Quant Alert Daemon...
python quant_alert_daemon.py %*

echo.
echo Daemon stopped.
pause

@echo off
cd /d "%~dp0"
title Quant Engine - Integrated Trading Desk
echo ========================================================
echo   Starting NIFTY ^& SENSEX F^&O Quantitative Engine...
echo ========================================================
echo.
call ".\.venv\Scripts\activate.bat"

echo Checking Background Alert Daemon status...
python -c "from telegram_notifier import is_daemon_active; exit(0 if is_daemon_active() else 1)"
if errorlevel 1 (
    echo [INFO] Launching Background Alert Daemon [quant_alert_daemon.py]...
    start "Quant Alert Daemon" /min python quant_alert_daemon.py
    ping 127.0.0.1 -n 3 >nul
) else (
    echo [INFO] Background Alert Daemon is already running.
)

echo.
echo Launching Cockpit in default browser...
start "" "http://localhost:8501"

echo Starting Streamlit Cockpit Web App...
streamlit run app.py
pause


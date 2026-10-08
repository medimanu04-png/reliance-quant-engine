@echo off
title Multi-Asset Live Quantitative Trading Desk
cls
echo =========================================================================
echo    NIFTY & SENSEX QUANTITATIVE F&O LIVE DESK (AUTO-APPENDING)
echo =========================================================================
echo.
cd /d "%~dp0"

IF EXIST ".venv\Scripts\python.exe" (
    echo [INFO] Activating virtual environment...
    ".venv\Scripts\python.exe" run_live_desk.py %*
) ELSE (
    echo [INFO] Using system python...
    python run_live_desk.py %*
)

pause

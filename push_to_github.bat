@echo off
cd /d "%~dp0"
title Nifty & Sensex Quant Engine — Git Sync (Local Master)
echo ===========================================================================
echo   Syncing Nifty & Sensex Quant Engine with GitHub [Local = Master Copy]
echo ===========================================================================
echo.

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" git_sync_manager.py
) else (
    echo [Fallback Native Git Sync...]
    git add -A
    git commit -m "chore(sync): local master update %date% %time%" >nul 2>&1
    git merge origin/main --no-edit -X ours >nul 2>&1
    git push origin main
    echo.
    echo Sync finished.
)

echo.
echo ===========================================================================
echo   Done! Local master copy is fully synchronized with GitHub origin/main.
echo ===========================================================================
timeout /t 5

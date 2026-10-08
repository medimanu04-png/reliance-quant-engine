@echo off
cd /d "%~dp0"
title Quant Engine
echo ========================================================
echo   Starting NIFTY & SENSEX F^&O Quantitative Engine...
echo ========================================================
echo.
call ".\.venv\Scripts\activate.bat"
streamlit run app.py
pause

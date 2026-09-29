@echo off
cd /d "%~dp0"
title RELIANCE Quant Engine
echo ========================================================
echo   Starting RELIANCE F^&O Quantitative Engine...
echo ========================================================
echo.
call ".\.venv\Scripts\activate.bat"
streamlit run app.py
pause

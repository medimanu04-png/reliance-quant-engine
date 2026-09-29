@echo off
title Stop Reliance Quant Alert Daemon
echo Stopping any running instances of quant_alert_daemon.py...
taskkill /F /FI "COMMANDLINE eq *quant_alert_daemon*" /T >nul 2>&1
powershell -NoProfile -Command "Get-Process python -ErrorAction SilentlyContinue | Where-Object { try { (Get-CimInstance Win32_Process -Filter \"ProcessId = $($_.Id)\").CommandLine -like '*quant_alert_daemon.py*' } catch { $false } } | Stop-Process -Force" >nul 2>&1
echo Done! Reliance Quant Alert Daemon has been stopped.
timeout /t 3

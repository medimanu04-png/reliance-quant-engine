@echo off
title Stop Reliance Quant Alert Daemon
echo Stopping any running instances of quant_alert_daemon.py...
taskkill /F /FI "COMMANDLINE eq *quant_alert_daemon*" /T >nul 2>&1
wmic process where "CommandLine like '%%quant_alert_daemon.py%%' and not CommandLine like '%%wmic%%'" call terminate >nul 2>&1
echo Done! Reliance Quant Alert Daemon has been stopped.
timeout /t 3

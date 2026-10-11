<#
.SYNOPSIS
    Automated Windows Task Scheduler Setup for Manoj Quant Engine

.DESCRIPTION
    Registers two scheduled tasks in Windows Task Scheduler:
    1. ManojQuant_PreMarketCheck: Runs Monday-Friday at 09:00 AM IST
    2. ManojQuant_EODDebrief: Runs Monday-Friday at 03:30 PM IST

.USAGE
    powershell -ExecutionPolicy Bypass -File .\schedule_market_tasks.ps1
#>

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PreMarketBat = Join-Path $ScriptDir "run_pre_market_health_check.bat"
$EodBat = Join-Path $ScriptDir "run_eod_session_summary.bat"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   Manoj Quant Engine - Windows Task Scheduler Setup       " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "Script Directory: $ScriptDir" -ForegroundColor Gray

# 1. Register Pre-Market 09:00 AM Task
$PreMarketTask = "ManojQuant_PreMarket_0900"
Write-Host "`n[1/2] Configuring $PreMarketTask at 09:00 AM IST (Mon-Fri)..." -ForegroundColor Yellow
$PreCmd = "schtasks /create /tn `"$PreMarketTask`" /tr `"`"$PreMarketBat`"`" /sc weekly /d MON,TUE,WED,THU,FRI /st 09:00 /f"
cmd.exe /c $PreCmd

# 2. Register EOD 03:30 PM Task
$EodTask = "ManojQuant_EOD_1530"
Write-Host "`n[2/2] Configuring $EodTask at 03:30 PM IST (Mon-Fri)..." -ForegroundColor Yellow
$EodCmd = "schtasks /create /tn `"$EodTask`" /tr `"`"$EodBat`"`" /sc weekly /d MON,TUE,WED,THU,FRI /st 15:30 /f"
cmd.exe /c $EodCmd

Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host "✅ Both scheduled tasks registered successfully!" -ForegroundColor Green
Write-Host "• 09:00 AM IST -> $PreMarketTask" -ForegroundColor Gray
Write-Host "• 03:30 PM IST -> $EodTask" -ForegroundColor Gray
Write-Host "==========================================================" -ForegroundColor Green

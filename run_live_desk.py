"""
1-Click Live Quantitative Trading Desk Launcher
===============================================
1. Generates fresh state for live_trade_dashboard.html.
2. Launches live_trade_dashboard.html in default web browser.
3. Starts the QuantAlertDaemon to monitor NIFTY and SENSEX 5m candles in real-time.
4. Auto-appends every live executed trade and continuously tracks in-flight trades.
"""

import os
import sys
import subprocess
import webbrowser
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DASHBOARD_FILE = os.path.join(BASE_DIR, "live_trade_dashboard.html")

def main():
    print("=" * 75)
    print("🚀 LAUNCHING MULTI-ASSET QUANTITATIVE LIVE TRADING DESK")
    print("=" * 75)
    print("Desk Targets   : NIFTY (130 Qty / 2L) | SENSEX (40 Qty / 2L)")
    print("Trading Hours  : 09:15 AM - 03:30 PM IST")
    print("Confluence Gate: Score >= 68.0%")
    print("=" * 75)

    # 1. Generate initial dashboard
    try:
        from live_dashboard_generator import generate_live_dashboard
        generate_live_dashboard()
        print("✅ Live Trade Dashboard compiled successfully!")
    except Exception as e:
        print(f"⚠️ Notice generating initial dashboard: {e}")

    # 2. Open dashboard in default browser
    if os.path.exists(DASHBOARD_FILE):
        print("🌐 Opening live_trade_dashboard.html in browser...")
        try:
            webbrowser.open(f"file:///{DASHBOARD_FILE}")
        except Exception as e:
            print(f"Could not open browser automatically: {e}")

    # 3. Launch quant alert daemon
    print("\n⚡ Starting 24/7 Multi-Asset Quant Engine Daemon...")
    time.sleep(1.0)
    
    # Import and run daemon directly
    try:
        from quant_alert_daemon import BenchmarkQuantAlertDaemon
        daemon = BenchmarkQuantAlertDaemon(
            interval_seconds=5.0,
            force_run="--now" in sys.argv,
            symbols=["NIFTY", "SENSEX"]
        )
        daemon.start()
    except KeyboardInterrupt:
        print("\n🛑 Desk stopped by user. All trades are safely persisted.")
    except Exception as e:
        print(f"❌ Daemon encountered error: {e}")

if __name__ == "__main__":
    main()

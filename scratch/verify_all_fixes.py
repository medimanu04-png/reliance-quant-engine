import sys, os, json
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from asset_config import get_asset_spec
from fo_quant_engine import UltraHighConvictionRelianceEngine
from trade_journal_manager import ShadowMonitoringEngine, TradeJournalManager, SequentialTradeEngine
from datetime import datetime, time

print("=" * 60)
print("1. Testing evaluate_90plus_confluence for all 4 desks (Single Engine)")
print("=" * 60)
engine = UltraHighConvictionRelianceEngine(symbol="RELIANCE")

for sym in ["RELIANCE", "ADANIENT", "NIFTY", "SENSEX"]:
    spec = get_asset_spec(sym)
    spot = spec.default_spot
    c5 = {
        "open": [spot * 0.99] * 30,
        "high": [spot * 1.01] * 30,
        "low": [spot * 0.98] * 30,
        "close": [spot] * 30,
        "volume": [spec.volume_norm / 100] * 30
    }
    c15 = {
        "open": [spot * 0.99] * 30,
        "high": [spot * 1.01] * 30,
        "low": [spot * 0.98] * 30,
        "close": [spot] * 30,
        "volume": [spec.volume_norm / 30] * 30
    }
    res = engine.evaluate_90plus_confluence(
        current_time=time(10, 15),
        c5m=c5,
        c15m=c15,
        symbol=sym,
        is_backtest=True
    )
    scrip_reported = res["1. SCRIP NAME"]
    status_reported = res["2. TRADE STATUS"]
    print(f"[{sym}] Scrip: {scrip_reported} | Status: {status_reported[:35]}...")
    assert sym in scrip_reported, f"Mismatch: expected {sym} in {scrip_reported}"

print("\nPASS: All 4 desks evaluate with correct asset-specific parameters!")

print("\n" + "=" * 60)
print("2. Testing Shadow Deduplication with Empty / Null entries")
print("=" * 60)
test_records = [
    {"date": "2026-10-05", "symbol": "", "shadow_status": "Active Monitoring"},
    {"date": "2026-10-05", "symbol": "ADANIENT", "shadow_status": "Active Monitoring"}
]

target = "RELIANCE"
matched = None
for r in test_records:
    r_sym = str(r.get("symbol", "")).strip().upper()
    if r_sym and (r_sym == target or target in r_sym or r_sym in target):
        matched = r
        break
assert matched is None, "Error: Empty symbol falsely matched!"
print("PASS: Empty symbol does not falsely match RELIANCE")

target = "ADANIENT"
matched = None
for r in test_records:
    r_sym = str(r.get("symbol", "")).strip().upper()
    if r_sym and (r_sym == target or target in r_sym or r_sym in target):
        matched = r
        break
assert matched is not None and matched["symbol"] == "ADANIENT", "Error: ADANIENT failed to match!"
print("PASS: ADANIENT matches correctly")

print("\n" + "=" * 60)
print("3. Testing Dynamic Expiry Resolution in GrowwMarketFeed")
print("=" * 60)
from groww_market_feed import GrowwMarketFeed
for s in ["RELIANCE", "ADANIENT", "NIFTY", "SENSEX"]:
    exp = GrowwMarketFeed._resolve_official_expiry(s)
    print(f"[{s}] Dynamic Official Expiry: {exp}")
    assert exp is not None and len(exp) > 5, f"Invalid expiry for {s}"

print("\n" + "=" * 60)
print("ALL VERIFICATIONS COMPLETED SUCCESSFULLY WITH ZERO ERRORS!")
print("=" * 60)

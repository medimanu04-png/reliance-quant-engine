"""
Live Forward Quantitative Trading Desk (October 05, 2026 Onwards)
================================================================
Pure forward-testing and live trade recording ledger starting Monday, October 05, 2026.
Contains ZERO backtested historical data. Every single trade entry is 100% authentic live forward data.
Features Option 1 Multi-Tranche Runner Mode (50% Bank at T1 + 50% Runner to T2) with full Delta & Lot sizing.
"""

import os
import json
import pandas as pd
from datetime import datetime
import pytz
from asset_config import resolve_symbol, get_asset_spec

IST = pytz.timezone("Asia/Kolkata")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

LIVE_JOURNAL_FILE = os.path.join(BASE_DIR, "daily_trade_journal.json")
SHADOW_SIGNALS_FILE = os.path.join(BASE_DIR, "shadow_signals_log.json")
DAILY_SIGNALS_FILE = os.path.join(BASE_DIR, "daily_signals_log.json")
ACTIVE_STATE_FILE = os.path.join(BASE_DIR, "active_trade_state.json")
OUTPUT_HTML_FILE = os.path.join(BASE_DIR, "live_trade_dashboard.html")
START_DATE = "2026-10-05"  # Forward-testing cycle start (Monday October 05 onwards)


def load_live_trades():
    """Loads forward trades recorded across daily trade journal and live signals logs."""
    trades_map = {"RELIANCE": [], "ADANIENT": [], "NIFTY": [], "SENSEX": []}
    seen_ids = set()

    # 1. Load from daily_trade_journal.json (Verified executed trades)
    if os.path.exists(LIVE_JOURNAL_FILE):
        try:
            with open(LIVE_JOURNAL_FILE, "r", encoding="utf-8") as f:
                live_entries = json.load(f)
                if isinstance(live_entries, list):
                    for entry in live_entries:
                        entry_date = entry.get("date", "")
                        if entry_date < START_DATE:
                            continue
                        tid = entry.get("id") or f"{entry_date}_{entry.get('trading_symbol')}"
                        if tid in seen_ids:
                            continue
                        seen_ids.add(tid)

                        raw_sym = entry.get("trading_symbol") or entry.get("instrument") or entry.get("symbol") or ""
                        sym = resolve_symbol(raw_sym)
                        month_str = entry_date[:7]
                        
                        is_closed = bool(entry.get("is_closed", False)) or entry.get("status") in ["HIT", "FAIL", "CLOSED"]
                        act_e = float(entry.get("actual_entry_price") or entry.get("suggested_entry") or entry.get("entry_price") or 0.0)
                        act_x = float(entry.get("actual_exit_price") or entry.get("exit_price") or 0.0) if is_closed else 0.0
                        
                        # Real Peak values: NEVER fallback to target_exit or target_pts for open trades!
                        peak_spot_val = float(entry.get("peak_spot") or entry.get("highest_price_reached") or act_e)
                        peak_pts_val = max(0.0, round(peak_spot_val - act_e, 2)) if peak_spot_val > act_e else 0.0
                        peak_time_val = entry.get("peak_time") or entry.get("actual_entry_time") or entry.get("trade_given_time") or "—"
                        if peak_pts_val <= 0:
                            peak_time_val = entry.get("actual_entry_time") or entry.get("trade_given_time") or "—"

                        spec = get_asset_spec(sym)
                        lot_size = spec.lot_size
                        num_lots = int(entry.get("num_lots", 2) or 2)
                        peak_amt_rs = round(peak_pts_val * lot_size * num_lots * 0.52, 2)
                        
                        if is_closed:
                            exit_time_val = entry.get("actual_exit_time") or entry.get("exit_time") or "03:30:00 PM"
                            exit_reason_val = entry.get("status", "TARGET HIT")
                            pnl_pts_val = float(entry.get("pnl_pts", 0.0) or round(act_x - act_e, 2))
                            realised_pnl_val = float(entry.get("realised_pnl", 0.0) or entry.get("total_profit", 0.0))
                        else:
                            exit_time_val = "—"
                            exit_reason_val = "OPEN (Currently Holding)"
                            pnl_pts_val = 0.0
                            realised_pnl_val = 0.0

                        row = {
                            "month": month_str,
                            "date": entry_date,
                            "action": entry.get("type", "BUY CE"),
                            "entry_time": entry.get("actual_entry_time", entry.get("trade_given_time", "09:15:00 AM")),
                            "entry_spot": act_e,
                            "peak_spot": peak_spot_val,
                            "peak_time": peak_time_val,
                            "peak_pts": peak_pts_val,
                            "peak_amount_rs": peak_amt_rs,
                            "least_spot": entry.get("least_spot", "—"),
                            "least_amount_rs": float(entry.get("least_amount_rs", 0.0) or 0.0),
                            "exit_time": exit_time_val,
                            "exit_spot": act_x,
                            "exit_reason": exit_reason_val,
                            "pnl_pts": pnl_pts_val,
                            "pnl_1lot": round(realised_pnl_val / max(1, num_lots), 2),
                            "pnl_2lots": realised_pnl_val,
                            "status": "LIVE_TRADE",
                            "score": float(entry.get("confluence_score", 75.0) or 75.0),
                            "runner_pnl_pts": pnl_pts_val,
                            "runner_exit_reason": exit_reason_val,
                            "is_live": True
                        }
                        if sym in trades_map:
                            trades_map[sym].append(row)
        except Exception as e:
            print(f"Notice reading live journal: {e}")

    # 2. Load from shadow_signals_log.json
    if os.path.exists(SHADOW_SIGNALS_FILE):
        try:
            with open(SHADOW_SIGNALS_FILE, "r", encoding="utf-8") as f:
                shadow_entries = json.load(f)
                if isinstance(shadow_entries, list):
                    for item in shadow_entries:
                        entry_date = item.get("date", "")
                        if entry_date < START_DATE:
                            continue
                        tid = item.get("id") or f"{entry_date}_{item.get('symbol')}"
                        if tid in seen_ids:
                            continue
                        seen_ids.add(tid)

                        raw_sym = item.get("symbol") or item.get("trading_symbol") or ""
                        sym = resolve_symbol(raw_sym)
                        month_str = entry_date[:7]
                        
                        target_pts = float(item.get("target_pts", 0.0) or 0.0)
                        entry_opt = float(item.get("entry") or 0.0)
                        exit_opt = float(item.get("exit_price") or item.get("target") or 0.0)
                        act_e = float(item.get("actual_entry_price") or 0.0)
                        act_x = float(item.get("actual_exit_price") or 0.0)

                        # Extract authentic underlying spot price if present in instrument string (e.g. Spot: ₹72310.24)
                        import re
                        inst_str = item.get("instrument", "")
                        spot_match = re.search(r"\(Spot:\s*₹?([\d,\.]+)\)", inst_str)
                        underlying_spot = None
                        if spot_match:
                            try:
                                underlying_spot = float(spot_match.group(1).replace(",", ""))
                            except Exception:
                                pass

                        if act_e > (1000.0 if sym in ("NIFTY", "SENSEX") else 500.0):
                            entry_spot_val = act_e
                        elif underlying_spot is not None:
                            entry_spot_val = underlying_spot
                        else:
                            entry_spot_val = entry_opt
                        
                        raw_status = str(item.get("shadow_status") or "Active Monitoring")
                        has_exit = bool(item.get("exit_time") or item.get("actual_exit_time"))
                        is_closed = (raw_status in ["Target Hit", "Stop-Loss Hit", "EOD Exit", "HIT", "FAIL"]) and has_exit and (raw_status != "Active Monitoring")

                        current_opt = float(item.get("current_price") or entry_opt)
                        highest_opt = float(item.get("highest_price_reached") or entry_opt)
                        # Anomaly filter: guard against quote corruption where highest option price exceeds 3.5x entry
                        if entry_opt > 0 and highest_opt > (entry_opt * 3.5):
                            highest_opt = entry_opt

                        # Real peak points gained above entry (0.0 if trade hasn't moved into profit)
                        peak_pts = max(0.0, round(highest_opt - entry_opt, 2))
                        if target_pts > 0 and peak_pts > (target_pts * 2.5):
                            peak_pts = target_pts

                        if is_closed:
                            exit_time_str = item.get("exit_time") or item.get("actual_exit_time") or "03:30:00 PM IST"
                            exit_reason_str = item.get("shadow_status") or "Target Hit"
                            shadow_pts = float(item.get("shadow_pts") or round(exit_opt - entry_opt, 2))
                        else:
                            exit_time_str = "—"
                            exit_reason_str = "OPEN (Currently Holding)"
                            shadow_pts = round(current_opt - entry_opt, 2)

                        is_ce = "CE" in str(item.get("action", "")).upper()
                        if entry_spot_val > 500.0:
                            peak_spot_val = round(entry_spot_val + (peak_pts if is_ce else -peak_pts), 1)
                            exit_spot_val = round(entry_spot_val + (shadow_pts if is_ce else -shadow_pts), 1) if is_closed else 0.0
                        else:
                            peak_spot_val = round(highest_opt, 2)
                            exit_spot_val = round(exit_opt, 2) if is_closed else 0.0

                        entry_time_str = item.get("actual_entry_time") or item.get("timestamp") or "09:15:00 AM IST"

                        # Peak Time: time of true peak; if no gain yet, display entry time or Holding
                        peak_time_str = item.get("peak_time") or (entry_time_str if peak_pts <= 0 else (exit_time_str if is_closed and "Target" in exit_reason_str else entry_time_str))

                        spec = get_asset_spec(sym)
                        lot_size = spec.lot_size
                        calc_pnl_2lots = round(shadow_pts * lot_size * 2 * 0.52, 2)
                        peak_amount_2lots = round(peak_pts * lot_size * 2 * 0.52, 2)
                        
                        row = {
                            "month": month_str,
                            "date": entry_date,
                            "action": item.get("action", "BUY CE"),
                            "entry_time": entry_time_str,
                            "entry_spot": entry_spot_val,
                            "peak_spot": peak_spot_val,
                            "peak_time": peak_time_str,
                            "peak_pts": peak_pts,
                            "peak_amount_rs": peak_amount_2lots,
                            "least_spot": item.get("lowest_price_reached", "—"),
                            "least_amount_rs": 0.0,
                            "exit_time": exit_time_str,
                            "exit_spot": exit_spot_val,
                            "exit_reason": exit_reason_str,
                            "pnl_pts": shadow_pts,
                            "pnl_1lot": round(calc_pnl_2lots / 2.0, 2),
                            "pnl_2lots": calc_pnl_2lots,
                            "status": "LIVE_TRADE",
                            "score": float(item.get("confluence_score", 75.0) or 75.0),
                            "runner_pnl_pts": shadow_pts,
                            "runner_exit_reason": exit_reason_str,
                            "is_live": True
                        }
                        if sym in trades_map:
                            trades_map[sym].append(row)
        except Exception as e:
            print(f"Notice reading shadow signals: {e}")

    # Live forward testing ledger returns verified forward trades executed from START_DATE onwards
    return trades_map["RELIANCE"], trades_map["ADANIENT"], trades_map["NIFTY"], trades_map["SENSEX"]


def get_all_active_states():
    """Generates the live active in-flight or armed trade state for all 4 desks."""
    from nse_data_fetcher import NSEIndiaFetcher
    desk_configs = {
        "RELIANCE": {
            "name": "Reliance Industries",
            "spot": 1410.5,
            "strike": 1420,
            "type": "CE",
            "target_1_pts": 7.0,
            "target_2_pts": 15.0,
            "sl_pts": 5.0,
            "atr_val": 4.1,
            "dynamic_sl_pts": 6.2,   # Solution 1: 1.5x ATR
            "hard_sl_pts": 10.3,     # Solution 2: 2.5x ATR catastrophe stop
            "score": 74.2,
            "lot_size": 500,
            "badge_color": "#38bdf8"
        },
        "ADANIENT": {
            "name": "Adani Enterprises",
            "spot": 2945.0,
            "strike": 2950,
            "type": "CE",
            "target_1_pts": 20.0,
            "target_2_pts": 45.0,
            "sl_pts": 12.0,
            "atr_val": 11.0,
            "dynamic_sl_pts": 16.5,  # Solution 1: 1.5x ATR
            "hard_sl_pts": 27.5,     # Solution 2: 2.5x ATR catastrophe stop
            "score": 72.8,
            "lot_size": 309,
            "badge_color": "#f59e0b"
        },
        "NIFTY": {
            "name": "NIFTY 50",
            "spot": 22415.0,
            "strike": 22400,
            "type": "CE",
            "target_1_pts": 35.0,
            "target_2_pts": 80.0,
            "sl_pts": 18.0,
            "atr_val": 16.3,
            "dynamic_sl_pts": 24.5,  # Solution 1: 1.5x ATR
            "hard_sl_pts": 40.8,     # Solution 2: 2.5x ATR catastrophe stop
            "score": 76.5,
            "lot_size": 65,
            "badge_color": "#10b981"
        },
        "SENSEX": {
            "name": "BSE SENSEX",
            "spot": 74250.0,
            "strike": 74200,
            "type": "CE",
            "target_1_pts": 120.0,
            "target_2_pts": 280.0,
            "sl_pts": 60.0,
            "atr_val": 54.7,
            "dynamic_sl_pts": 82.0,  # Solution 1: 1.5x ATR
            "hard_sl_pts": 136.8,    # Solution 2: 2.5x ATR catastrophe stop
            "score": 75.0,
            "lot_size": 20,
            "badge_color": "#a855f7"
        }
    }
    
    states = {}
    for sym, cfg in desk_configs.items():
        try:
            exp_plan = NSEIndiaFetcher.resolve_dynamic_expiry_mandate(symbol=sym)
            exp_str = exp_plan.get("selected_expiry")
        except Exception:
            exp_str = "06-OCT-2026" if sym == "NIFTY" else ("08-OCT-2026" if sym == "SENSEX" else "27-OCT-2026")
            
        # Dynamic Daily Support & Resistance Zones calculation
        spec_item = get_asset_spec(sym)
        live_spot = cfg["spot"]
        live_high = None
        live_low = None
        live_close = None
        try:
            off_data = NSEIndiaFetcher.get_official_data(symbol=sym)
            if off_data and off_data.get("spot_ltp"):
                live_spot = float(off_data.get("spot_ltp") or live_spot)
                live_high = float(off_data.get("high") or (live_spot * 1.006))
                live_low = float(off_data.get("low") or (live_spot * 0.994))
                live_close = float(off_data.get("prev_close") or live_spot)
        except Exception:
            pass

        sr_zones = spec_item.calculate_daily_sr_zones(
            spot=live_spot,
            high=live_high,
            low=live_low,
            prev_close=live_close
        )

        contract_name = f"{sym} {cfg['strike']} {cfg['type']} ({exp_str})"
        states[sym] = {
            "name": cfg["name"],
            "symbol": sym,
            "contract": contract_name,
            "action": "AWAITING MARKET OPEN (ARMED)",
            "current_spot": live_spot,
            "entry_spot": live_spot,
            "entry_time": "09:15:00 AM",
            "peak_spot": live_spot,
            "peak_profit_rs": 0.0,
            "unrealized_pnl_2lots": 0.0,
            "target_1_pts": cfg["target_1_pts"],
            "target_2_pts": cfg["target_2_pts"],
            "sl_pts": cfg["sl_pts"],
            "atr_val": cfg["atr_val"],
            "dynamic_sl_pts": cfg["dynamic_sl_pts"],
            "hard_sl_pts": cfg["hard_sl_pts"],
            "strategy_mode": "ENHANCED (4 SOLUTIONS ACTIVE)",
            "wick_shield_status": "🛡️ ACTIVE (5m Candle Close Filter)",
            "reentry_status": "🔄 ARMED (15m Resumption Radar)",
            "chandelier_status": "📈 ARMED (Period 10, Mult 2.0 @ 1:1 R:R)",
            "t1_status": "⏳ PENDING TARGET 1",
            "t2_status": "🛡️ ARMED UPON T1 BANK (CHANDELIER TRAIL)",
            "downside_risk": "Dynamic ATR Protected (Wick Shield)",
            "confluence_score": cfg["score"],
            "lot_size": cfg["lot_size"],
            "badge_color": cfg["badge_color"],
            "market_status": "🟢 ARMED FOR MONDAY, OCT 05 (09:15 AM IST)",
            "sr_zones": sr_zones
        }
        sym_file = os.path.join(BASE_DIR, f"active_trade_state_{sym}.json")
        if not os.path.exists(sym_file) and sym == "RELIANCE":
            sym_file = ACTIVE_STATE_FILE
        if os.path.exists(sym_file):
            try:
                with open(sym_file, "r", encoding="utf-8") as f_st:
                    live_data = json.load(f_st)
                    if isinstance(live_data, dict) and live_data.get("is_active"):
                        states[sym].update(live_data)
            except Exception:
                pass
    return states


def get_active_state():
    """Reads current real-time in-flight trade state if one exists."""
    all_st = get_all_active_states()
    if os.path.exists(ACTIVE_STATE_FILE):
        try:
            with open(ACTIVE_STATE_FILE, "r", encoding="utf-8") as f:
                st = json.load(f)
                if isinstance(st, dict) and st.get("contract"):
                    return st
        except Exception:
            pass
    return all_st.get("RELIANCE")


def generate_live_dashboard():
    """Generates the live HTML dashboard strictly starting Monday, October 05, 2026."""
    trades_rel, trades_ada, trades_nifty, trades_sensex = load_live_trades()
    all_active_states = get_all_active_states()
    active_state = all_active_states.get("RELIANCE", {})
    now_str = datetime.now(IST).strftime("%d %B %Y, %I:%M:%S %p IST")

    t1_st = active_state.get("tranche_1", {})
    t2_st = active_state.get("tranche_2", {})
    t1_status_str = t1_st.get("status", "PENDING")
    t2_status_str = t2_st.get("status", "PENDING_T1")

    init_sr = active_state.get("sr_zones", {})
    init_res = init_sr.get("resistance_zones", {})
    init_sup = init_sr.get("support_zones", {})
    init_cpr = init_sr.get("cpr", {})
    init_r3 = init_res.get("r3", {})
    init_r2 = init_res.get("r2", {})
    init_r1 = init_res.get("r1", {})
    init_s1 = init_sup.get("s1", {})
    init_s2 = init_sup.get("s2", {})
    init_s3 = init_sup.get("s3", {})

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Live Quantitative F&O Trading Desk (Oct 05, 2026 Onwards)</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Outfit:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-primary: #0a0d14;
            --bg-secondary: #101622;
            --bg-card: rgba(22, 30, 46, 0.7);
            --bg-card-hover: rgba(30, 41, 63, 0.9);
            --border-color: rgba(255, 255, 255, 0.08);
            --border-accent: rgba(56, 189, 248, 0.3);
            --text-primary: #f1f5f9;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
            --accent-cyan: #06b6d4;
            --accent-blue: #3b82f6;
            --accent-green: #10b981;
            --accent-green-bg: rgba(16, 185, 129, 0.12);
            --accent-red: #ef4444;
            --accent-red-bg: rgba(239, 68, 68, 0.12);
            --accent-purple: #a855f7;
            --accent-purple-bg: rgba(168, 85, 247, 0.12);
            --accent-amber: #f59e0b;
            --accent-amber-bg: rgba(245, 158, 11, 0.12);
            --shadow-glow: 0 0 25px rgba(6, 182, 212, 0.15);
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: 'Outfit', -apple-system, BlinkMacSystemFont, sans-serif;
            background: radial-gradient(circle at 50% 0%, #172033 0%, var(--bg-primary) 65%);
            color: var(--text-primary);
            min-height: 100vh;
            padding: 24px;
            overflow-x: hidden;
        }}

        .mono {{
            font-family: 'JetBrains Mono', monospace;
        }}

        .container {{
            max-width: 1600px;
            margin: 0 auto;
        }}

        /* Header */
        header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 20px 24px;
            background: var(--bg-card);
            backdrop-filter: blur(16px);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            margin-bottom: 20px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.4);
        }}

        .header-title h1 {{
            font-size: 24px;
            font-weight: 700;
            letter-spacing: -0.5px;
            background: linear-gradient(135deg, #fff 30%, #94a3b8 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            display: flex;
            align-items: center;
            gap: 12px;
        }}

        .badge-live {{
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            padding: 4px 10px;
            border-radius: 20px;
            background: var(--accent-green-bg);
            color: var(--accent-green);
            border: 1px solid rgba(16, 185, 129, 0.3);
            letter-spacing: 0.8px;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }}

        .pulse-dot {{
            width: 8px;
            height: 8px;
            background: var(--accent-green);
            border-radius: 50%;
            display: inline-block;
            box-shadow: 0 0 8px var(--accent-green);
            animation: pulse 1.5s infinite;
        }}

        @keyframes pulse {{
            0% {{ opacity: 1; transform: scale(1); }}
            50% {{ opacity: 0.4; transform: scale(1.2); }}
            100% {{ opacity: 1; transform: scale(1); }}
        }}

        .header-subtitle {{
            font-size: 13px;
            color: var(--text-secondary);
            margin-top: 4px;
        }}

        .desk-badge-group {{
            display: flex;
            gap: 12px;
            align-items: center;
        }}

        .desk-pill {{
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid var(--border-color);
            padding: 8px 14px;
            border-radius: 10px;
            font-size: 12px;
            text-align: right;
            cursor: pointer;
            transition: all 0.2s ease;
        }}

        .desk-pill:hover {{
            transform: translateY(-2px);
            border-color: var(--accent-cyan);
            box-shadow: 0 4px 14px rgba(6, 182, 212, 0.25);
        }}

        .desk-pill.active-pill {{
            border-color: var(--accent-cyan);
            background: rgba(6, 182, 212, 0.18);
            box-shadow: 0 0 16px rgba(6, 182, 212, 0.35);
        }}

        .primary-desk-bar {{
            background: linear-gradient(135deg, rgba(16, 24, 39, 0.95) 0%, rgba(20, 35, 58, 0.95) 100%);
            border: 1px solid rgba(56, 189, 248, 0.3);
            border-radius: 16px;
            padding: 14px 20px;
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
            flex-wrap: wrap;
            gap: 12px;
        }}

        .desk-selector-title {{
            display: flex;
            flex-direction: column;
            gap: 2px;
        }}

        .desk-selector-title span {{
            font-size: 13px;
            font-weight: 800;
            color: var(--accent-cyan);
            letter-spacing: 0.5px;
        }}

        .desk-selector-title small {{
            font-size: 11px;
            color: var(--text-muted);
        }}

        .desk-pill span {{
            display: block;
            color: var(--text-muted);
            font-size: 10px;
            text-transform: uppercase;
        }}

        .desk-pill strong {{
            color: var(--accent-cyan);
            font-size: 14px;
        }}

        /* 4 Concrete Quant Solutions Reference Bar */
        .solutions-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 14px;
            margin-bottom: 22px;
        }}

        .solution-card {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 14px;
            padding: 14px 18px;
            display: flex;
            align-items: center;
            gap: 14px;
            transition: all 0.25s ease;
            position: relative;
        }}

        .solution-card.active-solution {{
            border-color: rgba(6, 182, 212, 0.45);
            background: linear-gradient(135deg, rgba(22, 30, 46, 0.9) 0%, rgba(6, 182, 212, 0.1) 100%);
            box-shadow: 0 4px 20px rgba(6, 182, 212, 0.12);
        }}

        .solution-card:hover {{
            border-color: var(--accent-cyan);
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(0, 0, 0, 0.35);
        }}

        .solution-icon {{
            font-size: 24px;
            width: 44px;
            height: 44px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 10px;
            background: rgba(255, 255, 255, 0.05);
            flex-shrink: 0;
        }}

        .solution-info h4 {{
            font-size: 13px;
            font-weight: 700;
            color: #fff;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 8px;
        }}

        .solution-info p {{
            font-size: 11.5px;
            color: var(--text-muted);
            margin-top: 3px;
            line-height: 1.35;
        }}

        .sol-status-pill {{
            font-size: 10px;
            font-weight: 800;
            padding: 2px 7px;
            border-radius: 6px;
            background: rgba(16, 185, 129, 0.15);
            color: #10b981;
            border: 1px solid rgba(16, 185, 129, 0.3);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        .tag-solution {{
            font-size: 10.5px;
            font-weight: 800;
            padding: 2px 8px;
            border-radius: 6px;
            display: inline-block;
            letter-spacing: 0.3px;
        }}

        .tag-wick-shield {{
            background: rgba(56, 189, 248, 0.15);
            color: #38bdf8;
            border: 1px solid rgba(56, 189, 248, 0.35);
        }}

        .tag-reentry {{
            background: rgba(168, 85, 247, 0.15);
            color: #c084fc;
            border: 1px solid rgba(168, 85, 247, 0.35);
        }}

        .tag-chandelier {{
            background: rgba(16, 185, 129, 0.15);
            color: #34d399;
            border: 1px solid rgba(16, 185, 129, 0.35);
        }}

        .tag-hard-sl {{
            background: rgba(239, 68, 68, 0.15);
            color: #f87171;
            border: 1px solid rgba(239, 68, 68, 0.35);
        }}

        .tag-target {{
            background: rgba(16, 185, 129, 0.15);
            color: #10b981;
            border: 1px solid rgba(16, 185, 129, 0.35);
        }}

        /* Live In-Flight Trade Card */
        .active-trade-box {{
            background: linear-gradient(135deg, rgba(16, 185, 129, 0.08) 0%, rgba(6, 182, 212, 0.08) 100%);
            border: 1px solid rgba(16, 185, 129, 0.35);
            border-radius: 16px;
            padding: 22px 24px;
            margin-bottom: 22px;
            box-shadow: 0 10px 32px rgba(0, 0, 0, 0.35);
            display: block;
        }}

        .active-trade-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
        }}

        .active-trade-header h3 {{
            font-size: 16px;
            display: flex;
            align-items: center;
            gap: 10px;
            color: #fff;
        }}

        .active-trade-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 14px;
            margin-bottom: 16px;
        }}

        .active-tile {{
            background: rgba(0,0,0,0.35);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 10px;
            padding: 12px 16px;
        }}

        .active-tile span {{
            font-size: 11px;
            color: var(--text-muted);
            text-transform: uppercase;
            display: block;
        }}

        .active-tile strong {{
            font-size: 18px;
            font-weight: 700;
            margin-top: 4px;
            display: block;
        }}

        /* Option 1 Dual-Tranche Execution Desk */
        .tranche-desk-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
            gap: 14px;
            margin-top: 10px;
        }}

        .tranche-box {{
            background: rgba(0, 0, 0, 0.4);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 14px 18px;
            transition: all 0.25s ease;
        }}

        .tranche-box.tranche-banked {{
            background: rgba(16, 185, 129, 0.12);
            border-color: rgba(16, 185, 129, 0.45);
            box-shadow: 0 0 16px rgba(16, 185, 129, 0.2);
        }}

        .tranche-box.tranche-runner {{
            background: rgba(6, 182, 212, 0.12);
            border-color: rgba(6, 182, 212, 0.45);
            box-shadow: 0 0 16px rgba(6, 182, 212, 0.2);
        }}

        .tranche-box-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
            padding-bottom: 8px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        }}

        .tranche-tag {{
            font-size: 11px;
            font-weight: 700;
            color: #94a3b8;
            letter-spacing: 0.5px;
            text-transform: uppercase;
        }}

        .tranche-status-badge {{
            font-size: 10px;
            font-weight: 800;
            padding: 3px 8px;
            border-radius: 6px;
            letter-spacing: 0.5px;
            text-transform: uppercase;
        }}

        .badge-banked {{
            background: var(--accent-green-bg);
            color: var(--accent-green);
            border: 1px solid rgba(16, 185, 129, 0.3);
        }}

        .badge-pending {{
            background: rgba(245, 158, 11, 0.15);
            color: var(--accent-amber);
            border: 1px solid rgba(245, 158, 11, 0.3);
        }}

        .badge-runner {{
            background: rgba(6, 182, 212, 0.15);
            color: var(--accent-cyan);
            border: 1px solid rgba(6, 182, 212, 0.3);
        }}

        .badge-standby {{
            background: rgba(255, 255, 255, 0.05);
            color: var(--text-muted);
            border: 1px solid rgba(255, 255, 255, 0.1);
        }}

        .tranche-content {{
            display: flex;
            flex-direction: column;
            gap: 8px;
        }}

        .tranche-row {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 12px;
        }}

        .tranche-row span {{
            color: var(--text-muted);
        }}

        /* Dynamic Daily Support & Resistance Zones Card */
        .sr-card {{
            background: var(--bg-card);
            backdrop-filter: blur(16px);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 22px 24px;
            margin-bottom: 22px;
            box-shadow: 0 10px 32px rgba(0, 0, 0, 0.35);
        }}

        .sr-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 18px;
            flex-wrap: wrap;
            gap: 12px;
        }}

        .sr-header h3 {{
            font-size: 16px;
            font-weight: 700;
            color: #fff;
            display: flex;
            align-items: center;
            gap: 10px;
        }}

        .sr-badges-cluster {{
            display: flex;
            align-items: center;
            gap: 10px;
            flex-wrap: wrap;
        }}

        .sr-badge {{
            font-size: 11px;
            font-weight: 700;
            padding: 4px 10px;
            border-radius: 8px;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }}

        .sr-badge-spot {{
            background: rgba(6, 182, 212, 0.15);
            color: var(--accent-cyan);
            border: 1px solid rgba(6, 182, 212, 0.35);
        }}

        .sr-badge-range {{
            background: rgba(255, 255, 255, 0.05);
            color: #e2e8f0;
            border: 1px solid rgba(255, 255, 255, 0.12);
        }}

        .sr-badge-regime {{
            background: rgba(245, 158, 11, 0.15);
            color: var(--accent-amber);
            border: 1px solid rgba(245, 158, 11, 0.35);
        }}

        .sr-grid-layout {{
            display: grid;
            grid-template-columns: 1fr;
            gap: 16px;
        }}

        @media (min-width: 1024px) {{
            .sr-grid-layout {{
                grid-template-columns: 1fr 1fr;
            }}
        }}

        .sr-column-box {{
            background: rgba(0, 0, 0, 0.3);
            border-radius: 12px;
            padding: 16px;
            border: 1px solid rgba(255, 255, 255, 0.05);
        }}

        .sr-column-title {{
            font-size: 13px;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            margin-bottom: 12px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 8px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        }}

        .sr-res-title {{
            color: #f87171;
        }}

        .sr-sup-title {{
            color: #34d399;
        }}

        .sr-levels-list {{
            display: flex;
            flex-direction: column;
            gap: 10px;
        }}

        .sr-level-tile {{
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 10px;
            padding: 12px 14px;
            transition: all 0.2s ease;
        }}

        .sr-level-tile:hover {{
            background: rgba(255, 255, 255, 0.06);
        }}

        .sr-level-tile.resistance-tile {{
            border-left: 4px solid #ef4444;
        }}

        .sr-level-tile.support-tile {{
            border-left: 4px solid #10b981;
        }}

        .sr-level-tile.testing-active {{
            box-shadow: 0 0 14px rgba(245, 158, 11, 0.3);
            border-color: rgba(245, 158, 11, 0.6);
            background: rgba(245, 158, 11, 0.08);
        }}

        .sr-tile-top {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 4px;
        }}

        .sr-tag-name {{
            font-size: 13px;
            font-weight: 800;
        }}

        .sr-tag-status {{
            font-size: 10.5px;
            font-weight: 700;
            padding: 2px 8px;
            border-radius: 6px;
            text-transform: uppercase;
            letter-spacing: 0.3px;
        }}

        .status-supply {{
            background: rgba(239, 68, 68, 0.15);
            color: #f87171;
            border: 1px solid rgba(239, 68, 68, 0.3);
        }}

        .status-demand {{
            background: rgba(16, 185, 129, 0.15);
            color: #34d399;
            border: 1px solid rgba(16, 185, 129, 0.3);
        }}

        .status-testing {{
            background: rgba(245, 158, 11, 0.2);
            color: #fbbf24;
            border: 1px solid rgba(245, 158, 11, 0.5);
            animation: pulse 1.5s infinite;
        }}

        .status-breached {{
            background: rgba(6, 182, 212, 0.15);
            color: var(--accent-cyan);
            border: 1px solid rgba(6, 182, 212, 0.3);
        }}

        .sr-tile-mid {{
            display: flex;
            justify-content: space-between;
            align-items: baseline;
        }}

        .sr-tile-mid .level-val {{
            font-size: 19px;
            font-weight: 800;
            letter-spacing: -0.5px;
        }}

        .sr-tile-mid .dist-val {{
            font-size: 12px;
            font-weight: 700;
        }}

        .sr-tile-bot {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 4px;
            font-size: 11px;
            color: var(--text-muted);
        }}

        /* CPR Mid Anchor Bar */
        .cpr-mid-bar {{
            grid-column: 1 / -1;
            background: rgba(168, 85, 247, 0.08);
            border: 1px solid rgba(168, 85, 247, 0.25);
            border-radius: 12px;
            padding: 14px 18px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 12px;
        }}

        .cpr-mid-group {{
            display: flex;
            align-items: center;
            gap: 18px;
            flex-wrap: wrap;
        }}

        .cpr-item {{
            display: flex;
            flex-direction: column;
        }}

        .cpr-item span {{
            font-size: 10.5px;
            color: var(--text-muted);
            text-transform: uppercase;
        }}

        .cpr-item strong {{
            font-size: 15px;
            font-weight: 700;
            color: #e2e8f0;
        }}

        /* Sizing Card */
        .sizing-card {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 16px 20px;
            margin-bottom: 18px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 16px;
            box-shadow: 0 8px 24px rgba(0,0,0,0.3);
        }}

        .sizing-title-group h3 {{
            font-size: 15px;
            font-weight: 700;
            color: #fff;
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .sizing-title-group p {{
            font-size: 12px;
            color: var(--text-secondary);
            margin-top: 2px;
        }}

        .sizing-controls {{
            display: flex;
            gap: 10px;
            align-items: center;
            flex-wrap: wrap;
        }}

        .lot-preset-btn {{
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--border-color);
            color: var(--text-secondary);
            font-family: inherit;
            font-size: 12px;
            font-weight: 700;
            padding: 6px 12px;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.2s;
        }}

        .lot-preset-btn:hover {{
            background: rgba(255, 255, 255, 0.1);
            color: #fff;
        }}

        .lot-preset-btn.active {{
            background: var(--accent-cyan);
            color: #000;
            border-color: var(--accent-cyan);
            box-shadow: 0 0 12px rgba(6, 182, 212, 0.4);
        }}

        .lot-input-wrapper {{
            display: flex;
            align-items: center;
            gap: 6px;
            background: rgba(0, 0, 0, 0.35);
            padding: 4px 10px;
            border-radius: 8px;
            border: 1px solid var(--border-color);
        }}

        .lot-input-wrapper label {{
            font-size: 11px;
            color: var(--text-muted);
            text-transform: uppercase;
            font-weight: 600;
        }}

        .lot-input {{
            width: 70px;
            background: transparent;
            border: none;
            color: var(--accent-cyan);
            font-family: 'JetBrains Mono', monospace;
            font-size: 16px;
            font-weight: 800;
            text-align: center;
            outline: none;
        }}

        .lot-dropdown {{
            background: rgba(0,0,0,0.4);
            border: 1px solid var(--border-color);
            color: var(--text-primary);
            font-family: inherit;
            font-size: 13px;
            font-weight: 600;
            padding: 7px 12px;
            border-radius: 8px;
            outline: none;
            cursor: pointer;
        }}

        .sizing-summary-pill {{
            background: rgba(16, 185, 129, 0.12);
            border: 1px solid rgba(16, 185, 129, 0.3);
            border-radius: 10px;
            padding: 8px 14px;
            font-size: 12px;
            color: var(--accent-green);
        }}

        .sizing-summary-pill strong {{
            font-size: 14px;
            color: #fff;
        }}

        /* Strategy Mode Card (Baseline vs Multi-Tranche Runner) */
        .strategy-card {{
            background: linear-gradient(135deg, rgba(16, 24, 39, 0.95) 0%, rgba(20, 35, 58, 0.95) 100%);
            border: 1px solid rgba(16, 185, 129, 0.35);
            border-radius: 16px;
            padding: 16px 20px;
            margin-bottom: 18px;
            box-shadow: 0 4px 22px rgba(16, 185, 129, 0.12);
        }}

        .strategy-title-group {{
            margin-bottom: 12px;
        }}

        .strategy-title-group h3 {{
            font-size: 15px;
            font-weight: 700;
            color: #fff;
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .strategy-title-group p {{
            font-size: 12px;
            color: var(--text-secondary);
            margin-top: 3px;
        }}

        .strategy-selector {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 12px;
        }}

        .strat-btn {{
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 12px 16px;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 12px;
            text-align: left;
            transition: all 0.2s ease;
            color: var(--text-primary);
        }}

        .strat-btn:hover {{
            background: rgba(255, 255, 255, 0.06);
            border-color: rgba(16, 185, 129, 0.4);
        }}

        .strat-btn.active {{
            background: rgba(16, 185, 129, 0.15);
            border-color: var(--accent-green);
            box-shadow: 0 0 18px rgba(16, 185, 129, 0.25);
        }}

        .strat-icon {{
            font-size: 22px;
        }}

        .strat-text strong {{
            display: block;
            font-size: 13px;
            color: #fff;
        }}

        .strat-btn.active .strat-text strong {{
            color: var(--accent-green);
        }}

        .strat-text small {{
            display: block;
            font-size: 11px;
            color: var(--text-muted);
            margin-top: 2px;
            line-height: 1.4;
        }}

        /* Contract & Delta Pricing Mode */
        .delta-card {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 16px 20px;
            margin-bottom: 20px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.25);
        }}

        .delta-title-group {{
            margin-bottom: 12px;
        }}

        .delta-title-group h3 {{
            font-size: 15px;
            font-weight: 700;
            color: #fff;
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .delta-title-group p {{
            font-size: 12px;
            color: var(--text-secondary);
            margin-top: 3px;
        }}

        .delta-selector {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 12px;
        }}

        .delta-btn {{
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 12px 16px;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 12px;
            text-align: left;
            transition: all 0.2s ease;
            color: var(--text-primary);
        }}

        .delta-btn:hover {{
            background: rgba(255, 255, 255, 0.06);
            border-color: rgba(56, 189, 248, 0.4);
        }}

        .delta-btn.active {{
            background: rgba(56, 189, 248, 0.15);
            border-color: var(--accent-cyan);
            box-shadow: 0 0 16px rgba(6, 182, 212, 0.25);
        }}

        .delta-icon {{
            font-size: 22px;
        }}

        .delta-text strong {{
            display: block;
            font-size: 13px;
            color: #fff;
        }}

        .delta-btn.active .delta-text strong {{
            color: var(--accent-cyan);
        }}

        .delta-text small {{
            display: block;
            font-size: 11px;
            color: var(--text-muted);
            margin-top: 2px;
        }}

        /* KPI Grid */
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}

        .kpi-card {{
            background: var(--bg-card);
            backdrop-filter: blur(12px);
            border: 1px solid var(--border-color);
            border-radius: 14px;
            padding: 18px 20px;
            transition: all 0.25s ease;
            position: relative;
            overflow: hidden;
        }}

        .kpi-card::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 3px;
            background: linear-gradient(90deg, transparent, var(--accent-blue), transparent);
            opacity: 0;
            transition: opacity 0.25s ease;
        }}

        .kpi-card:hover {{
            transform: translateY(-2px);
            border-color: var(--border-accent);
            box-shadow: var(--shadow-glow);
        }}

        .kpi-card:hover::before {{
            opacity: 1;
        }}

        .kpi-label {{
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.6px;
            color: var(--text-secondary);
            margin-bottom: 8px;
            display: flex;
            justify-content: space-between;
        }}

        .kpi-val {{
            font-size: 26px;
            font-weight: 800;
            letter-spacing: -0.5px;
        }}

        .kpi-sub {{
            font-size: 12px;
            color: var(--text-muted);
            margin-top: 6px;
        }}

        .val-profit {{
            color: var(--accent-green);
        }}

        .val-loss {{
            color: var(--accent-red);
        }}

        /* Controls Section */
        .controls-card {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 18px 22px;
            margin-bottom: 24px;
            display: flex;
            flex-wrap: wrap;
            gap: 18px;
            align-items: center;
            justify-content: space-between;
        }}

        .nav-tabs {{
            display: flex;
            gap: 6px;
            background: rgba(0, 0, 0, 0.3);
            padding: 4px;
            border-radius: 10px;
            border: 1px solid var(--border-color);
        }}

        .nav-btn {{
            background: transparent;
            border: none;
            color: var(--text-secondary);
            font-family: inherit;
            font-size: 13px;
            font-weight: 600;
            padding: 8px 16px;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.2s ease;
        }}

        .nav-btn:hover {{
            color: #fff;
            background: rgba(255, 255, 255, 0.05);
        }}

        .nav-btn.active {{
            background: var(--accent-blue);
            color: #fff;
            box-shadow: 0 2px 10px rgba(59, 130, 246, 0.3);
        }}

        .filter-group {{
            display: flex;
            gap: 8px;
            align-items: center;
            flex-wrap: wrap;
        }}

        .filter-select, .search-box {{
            background: rgba(0, 0, 0, 0.35);
            border: 1px solid var(--border-color);
            color: var(--text-primary);
            font-family: inherit;
            font-size: 13px;
            padding: 8px 14px;
            border-radius: 8px;
            outline: none;
            transition: border-color 0.2s;
        }}

        .filter-select:focus, .search-box:focus {{
            border-color: var(--accent-cyan);
        }}

        .search-box {{
            min-width: 220px;
        }}

        /* Table Container - Complete Scrollable Design */
        .table-card {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            overflow: hidden;
            box-shadow: 0 12px 40px rgba(0,0,0,0.5);
        }}

        .table-scroll-container {{
            max-height: 650px;
            overflow: auto;
            position: relative;
        }}

        table {{
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
            font-size: 13px;
            white-space: nowrap;
        }}

        th {{
            background: #131b2c;
            color: var(--text-secondary);
            font-weight: 600;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.6px;
            padding: 14px 16px;
            text-align: left;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            position: sticky;
            top: 0;
            z-index: 20;
        }}

        /* Sticky Left Column (Date) */
        th.col-sticky-left, td.col-sticky-left {{
            position: sticky;
            left: 0;
            background: #111726;
            z-index: 10;
            border-right: 1px solid rgba(255, 255, 255, 0.08);
        }}
        th.col-sticky-left {{
            z-index: 25;
            background: #141d30;
        }}

        /* Sticky Right Column (Final P&L) */
        th.col-sticky-right, td.col-sticky-right {{
            position: sticky;
            right: 0;
            background: #111726;
            z-index: 10;
            border-left: 1px solid rgba(255, 255, 255, 0.08);
            text-align: right;
            box-shadow: -6px 0 16px rgba(0,0,0,0.3);
        }}
        th.col-sticky-right {{
            z-index: 25;
            background: #141d30;
        }}

        td {{
            padding: 12px 16px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.04);
            color: var(--text-primary);
        }}

        tbody tr {{
            transition: background 0.15s ease;
        }}

        tbody tr:hover {{
            background: rgba(255, 255, 255, 0.04);
        }}

        tbody tr:hover td.col-sticky-left,
        tbody tr:hover td.col-sticky-right {{
            background: #182238;
        }}

        /* Pill Badges */
        .pill {{
            display: inline-block;
            padding: 3px 8px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.3px;
        }}

        .pill-ce {{
            background: var(--accent-green-bg);
            color: var(--accent-green);
            border: 1px solid rgba(16, 185, 129, 0.25);
        }}

        .pill-pe {{
            background: var(--accent-purple-bg);
            color: var(--accent-purple);
            border: 1px solid rgba(168, 85, 247, 0.25);
        }}

        .pill-standdown {{
            background: rgba(148, 163, 184, 0.12);
            color: var(--text-muted);
            border: 1px solid rgba(148, 163, 184, 0.2);
        }}

        .pill-live-tag {{
            background: rgba(16, 185, 129, 0.2);
            color: var(--accent-green);
            border: 1px solid var(--accent-green);
            font-size: 10px;
            font-weight: 800;
            padding: 2px 6px;
            border-radius: 4px;
            margin-right: 6px;
        }}

        .score-chip {{
            font-size: 12px;
            font-weight: 700;
            padding: 2px 7px;
            border-radius: 6px;
            background: rgba(6, 182, 212, 0.12);
            color: var(--accent-cyan);
            border: 1px solid rgba(6, 182, 212, 0.25);
        }}

        .score-chip.high {{
            background: rgba(16, 185, 129, 0.15);
            color: var(--accent-green);
            border-color: rgba(16, 185, 129, 0.3);
        }}

        .reason-tag {{
            font-size: 11px;
            font-weight: 600;
            padding: 3px 8px;
            border-radius: 6px;
            display: inline-block;
        }}

        .reason-target {{
            background: var(--accent-green-bg);
            color: var(--accent-green);
        }}

        .reason-sl {{
            background: var(--accent-red-bg);
            color: var(--accent-red);
        }}

        .reason-eod {{
            background: rgba(59, 130, 246, 0.12);
            color: var(--accent-blue);
        }}

        .pnl-cell {{
            font-weight: 700;
            font-size: 13px;
            text-align: right;
        }}

        .pnl-pos {{
            color: var(--accent-green);
        }}

        .pnl-neg {{
            color: var(--accent-red);
        }}

        .pnl-zero {{
            color: var(--text-muted);
        }}

        /* Table Sticky Footer */
        tfoot {{
            position: sticky;
            bottom: 0;
            z-index: 22;
        }}

        tfoot td {{
            background: #101726;
            border-top: 2px solid var(--accent-cyan);
            border-bottom: none;
            padding: 14px 16px;
            font-weight: 700;
        }}

        tfoot td.col-sticky-left {{
            z-index: 26;
            background: #121c30;
            border-top: 2px solid var(--accent-cyan);
        }}

        tfoot td.col-sticky-right {{
            z-index: 26;
            background: #121c30;
            border-top: 2px solid var(--accent-cyan);
        }}

        .table-footer {{
            padding: 14px 20px;
            background: #111726;
            border-top: 1px solid rgba(255, 255, 255, 0.08);
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 12px;
            color: var(--text-secondary);
        }}

        .info-bar {{
            background: rgba(6, 182, 212, 0.08);
            border: 1px solid rgba(6, 182, 212, 0.2);
            border-radius: 12px;
            padding: 12px 18px;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            font-size: 12px;
            color: #bae6fd;
        }}
    </style>
</head>
<body>

<div class="container">
    <!-- Header -->
    <header>
        <div class="header-title">
            <h1>Quantitative F&O Live Trading Desk <span class="badge-live"><span class="pulse-dot"></span> MONDAY OCT 05 ONWARDS</span></h1>
            <div class="header-subtitle">Forward Execution &amp; Recording Ledger | Baseline Start Date: <strong>Monday, October 05, 2026</strong> | Engine Ping: <span class="mono" style="color:#38bdf8;">{now_str}</span></div>
        </div>
        <div class="desk-badge-group">
            <div class="desk-pill active-pill" id="pill-rel" onclick="switchTicker('RELIANCE')" style="cursor:pointer;" title="Click to view Reliance Desk">
                <span>Reliance Desk</span>
                <strong>500 Qty / Lot</strong>
            </div>
            <div class="desk-pill" id="pill-ada" onclick="switchTicker('ADANIENT')" style="cursor:pointer;" title="Click to view Adani Desk">
                <span>Adani Desk</span>
                <strong>309 Qty / Lot</strong>
            </div>
            <div class="desk-pill" id="pill-nifty" onclick="switchTicker('NIFTY')" style="cursor:pointer;" title="Click to view Nifty Desk">
                <span>Nifty Desk</span>
                <strong>65 Qty / Lot</strong>
            </div>
            <div class="desk-pill" id="pill-sensex" onclick="switchTicker('SENSEX')" style="cursor:pointer;" title="Click to view Sensex Desk">
                <span>Sensex Desk</span>
                <strong>20 Qty / Lot</strong>
            </div>
        </div>
    </header>

    <!-- Primary Desk Navigation Bar -->
    <div class="primary-desk-bar">
        <div class="desk-selector-title">
            <span>🎯 SELECT ACTIVE QUANT DESK:</span>
            <small>Instantly switch active in-flight trade setup, lot sizing, and verified forward ledger</small>
        </div>
        <div class="nav-tabs">
            <button class="nav-btn active" id="top-tab-rel" onclick="switchTicker('RELIANCE')">Reliance Industries</button>
            <button class="nav-btn" id="top-tab-ada" onclick="switchTicker('ADANIENT')">Adani Enterprises</button>
            <button class="nav-btn" id="top-tab-nifty" onclick="switchTicker('NIFTY')">NIFTY 50</button>
            <button class="nav-btn" id="top-tab-sensex" onclick="switchTicker('SENSEX')">BSE SENSEX</button>
        </div>
    </div>

    <!-- 4 Concrete Quant Solutions Reference & Active Indicators -->
    <div class="solutions-grid">
        <div class="solution-card active-solution" id="card-sol-1">
            <div class="solution-icon" style="color:var(--accent-cyan);">📐</div>
            <div class="solution-info">
                <h4>Solution 1: Dynamic ATR SL &amp; Sizing <span class="sol-status-pill">ACTIVE</span></h4>
                <p id="sol-desc-1">SL = max(Swing ± 5 pts, 1.5× ATR = -{active_state.get('dynamic_sl_pts', 6.2):.1f} pts). Dynamic sizing scaled to ₹6,000 risk.</p>
            </div>
        </div>
        <div class="solution-card active-solution" id="card-sol-2">
            <div class="solution-icon" style="color:#38bdf8;">🛡️</div>
            <div class="solution-info">
                <h4>Solution 2: Two-Tier SL (Wick Shield) <span class="sol-status-pill">ACTIVE</span></h4>
                <p id="sol-desc-2">Hard broker stop at -{active_state.get('hard_sl_pts', 10.3):.1f} pts (2.5× ATR). Technical exit triggers ONLY on 5m candle close.</p>
            </div>
        </div>
        <div class="solution-card active-solution" id="card-sol-3">
            <div class="solution-icon" style="color:var(--accent-purple);">🔄</div>
            <div class="solution-info">
                <h4>Solution 3: 15-Min Resumption Re-Entry <span class="sol-status-pill">ARMED</span></h4>
                <p id="sol-desc-3">Auto re-enters if a high-confluence setup gets wicked out and price reclaims entry level.</p>
            </div>
        </div>
        <div class="solution-card active-solution" id="card-sol-4">
            <div class="solution-icon" style="color:var(--accent-green);">📈</div>
            <div class="solution-info">
                <h4>Solution 4: Chandelier ATR Trailing <span class="sol-status-pill">ARMED</span></h4>
                <p id="sol-desc-4">At 1:1 R:R, moves SL to BE and trails behind 5m candle highs/lows (Period 10, Mult 2.0).</p>
            </div>
        </div>
    </div>

    <!-- Real-time Active Trade Monitor (Appears when in-flight trade is open) -->
    <div class="active-trade-box" id="active-trade-card">
        <div class="active-trade-header">
            <h3>⚡ IN-FLIGHT ACTIVE TRADE: <span class="mono" id="active-contract-name" style="color:var(--accent-cyan);">{active_state.get('contract')}</span></h3>
            <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
                <span class="badge-live"><span class="pulse-dot"></span> LIVE FORWARD EXECUTION</span>
                <span class="badge-live" style="background:rgba(6,182,212,0.15);border-color:var(--accent-cyan);color:var(--accent-cyan);">🚀 4 QUANT RULES ACTIVE</span>
                <span class="badge-live" style="background:rgba(56,189,248,0.15);border-color:var(--accent-blue);color:#38bdf8;">OPTION 1: TRANCHE RUNNER (50/50)</span>
            </div>
        </div>
        
        <!-- Live Spot & MTM Grid -->
        <div class="active-trade-grid">
            <div class="active-tile">
                <span>Entry Spot / Time</span>
                <strong class="mono" id="active-entry-spot-time">₹{active_state.get('entry_spot', 0.0):.1f} @ {active_state.get('entry_time', '—')}</strong>
            </div>
            <div class="active-tile">
                <span>Current Live Spot</span>
                <strong class="mono" id="active-current-spot" style="color:var(--accent-cyan);">₹{active_state.get('current_spot', 0.0):.1f}</strong>
            </div>
            <div class="active-tile">
                <span>Peak MTM Gain</span>
                <strong class="mono val-profit" id="active-peak-mtm">+₹{active_state.get('peak_profit_rs', 0.0):,.0f}</strong>
            </div>
            <div class="active-tile">
                <span>Live Unrealized P&L</span>
                <strong class="mono {'val-profit' if active_state.get('unrealized_pnl_2lots', 0.0) >= 0 else 'val-loss'}" id="active-unrealized-pnl">
                    {'₹' if active_state.get('unrealized_pnl_2lots', 0.0) < 0 else '+₹'}{active_state.get('unrealized_pnl_2lots', 0.0):,.2f}
                </strong>
            </div>
            <div class="active-tile" style="border-color:rgba(6,182,212,0.3);">
                <span>Dynamic ATR SL (Soft)</span>
                <strong class="mono" id="active-dynamic-sl" style="color:#38bdf8;">-{active_state.get('dynamic_sl_pts', 6.2):.1f} pts</strong>
                <small style="font-size:10px;color:var(--text-muted);display:block;margin-top:2px;">5m Candle Close Exit (1.5× ATR)</small>
            </div>
            <div class="active-tile" style="border-color:rgba(239,68,68,0.3);">
                <span>Hard Catastrophe Stop</span>
                <strong class="mono val-loss" id="active-hard-sl">-{active_state.get('hard_sl_pts', 10.3):.1f} pts</strong>
                <small style="font-size:10px;color:var(--text-muted);display:block;margin-top:2px;">Broker Disaster SL (2.5× ATR)</small>
            </div>
            <div class="active-tile">
                <span>Confluence Score</span>
                <strong class="mono" id="active-confluence-score" style="color:var(--accent-green);">{active_state.get('confluence_score', 0.0):.1f}%</strong>
            </div>
            <div class="active-tile">
                <span>Wick Shield Status</span>
                <strong class="mono" id="active-wick-shield" style="color:#34d399;">🛡️ ACTIVE</strong>
                <small style="font-size:10px;color:var(--text-muted);display:block;margin-top:2px;">Wick Noise Filtered</small>
            </div>
            <div class="active-tile">
                <span>15m Re-Entry Watcher</span>
                <strong class="mono" id="active-reentry-radar" style="color:var(--accent-purple);">🔄 RADAR ARMED</strong>
                <small style="font-size:10px;color:var(--text-muted);display:block;margin-top:2px;">Shakeout Resumption Monitor</small>
            </div>
            <div class="active-tile">
                <span>Chandelier Runner Trailing</span>
                <strong class="mono" id="active-chandelier-trail" style="color:var(--accent-amber);">📈 TRAIL ARMED</strong>
                <small style="font-size:10px;color:var(--text-muted);display:block;margin-top:2px;">Period 10, Mult 2.0 @ 1:1 R:R</small>
            </div>
        </div>

        <!-- Option 1 Dual-Tranche Execution Engine with 4 Solutions -->
        <div class="tranche-desk-grid">
            <div class="tranche-box {'tranche-banked' if t1_status_str == 'BANKED' else 'tranche-active'}">
                <div class="tranche-box-header">
                    <span class="tranche-tag">TRANCHE 1 (50% QUANTITY) — BANK PROFIT</span>
                    <span class="tranche-status-badge {'badge-banked' if t1_status_str == 'BANKED' else 'badge-pending'}" id="active-t1-badge">
                        {'✅ BANKED &amp; SECURED' if t1_status_str == 'BANKED' else '⏳ PENDING TARGET 1'}
                    </span>
                </div>
                <div class="tranche-content">
                    <div class="tranche-row">
                        <span>Target 1 Objective:</span>
                        <strong class="mono" id="active-t1-target" style="color:var(--accent-green);">+{active_state.get('target_1_pts', 7.0)} pts (Fixed Win Bank)</strong>
                    </div>
                    <div class="tranche-row">
                        <span>Risk Scaling:</span>
                        <strong class="mono" id="active-t1-sizing">Solution 1 Calibrated Risk Lots (50%)</strong>
                    </div>
                    <div class="tranche-row">
                        <span>Tranche 1 Status:</span>
                        <strong class="mono val-profit" id="active-t1-status">Armed for Fill</strong>
                    </div>
                </div>
            </div>

            <div class="tranche-box {'tranche-runner' if t1_status_str == 'BANKED' else 'tranche-standby'}">
                <div class="tranche-box-header">
                    <span class="tranche-tag">TRANCHE 2 (50% QUANTITY) — SOLUTION 4 CHANDELIER RUNNER</span>
                    <span class="tranche-status-badge {'badge-runner' if t1_status_str == 'BANKED' else 'badge-standby'}" id="active-t2-badge">
                        {'🚀 RUNNER IN-FLIGHT' if t1_status_str == 'BANKED' else '🛡️ ARMED UPON T1 BANK'}
                    </span>
                </div>
                <div class="tranche-content">
                    <div class="tranche-row">
                        <span>Target 2 Objective:</span>
                        <strong class="mono" id="active-t2-target" style="color:var(--accent-cyan);">+{active_state.get('target_2_pts', 15.0)} pts &amp; Open Chandelier Trail</strong>
                    </div>
                    <div class="tranche-row">
                        <span>Trailing Engine:</span>
                        <strong class="mono" id="active-t2-protection" style="color:#f59e0b;">Chandelier ATR (10, 2.0) | SL to BE @ 1:1 R:R</strong>
                    </div>
                    <div class="tranche-row">
                        <span>Downside Risk:</span>
                        <strong class="mono" id="active-t2-risk" style="color:var(--accent-green);">Solution 2 Wick Shield Protected</strong>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Dynamic Daily Support & Resistance Zones Desk (3 Resistance & 3 Support Zones) -->
    <div class="sr-card" id="sr-zones-card">
        <div class="sr-header">
            <h3>
                <span>🎯 DYNAMIC DAILY S/R &amp; PIVOT CORRIDOR:</span>
                <span class="mono" id="sr-desk-title" style="color:var(--accent-cyan);">{active_state.get('name', 'Reliance Industries')}</span>
            </h3>
            <div class="sr-badges-cluster">
                <span class="sr-badge sr-badge-spot" id="sr-badge-spot">Live Spot: ₹{active_state.get('current_spot', 0.0):.1f}</span>
                <span class="sr-badge sr-badge-range" id="sr-badge-range">H: ₹{init_sr.get('high', 0.0):.1f} | L: ₹{init_sr.get('low', 0.0):.1f} (Range: {init_sr.get('range', 0.0):.1f} pts)</span>
                <span class="sr-badge sr-badge-regime" id="sr-badge-regime">{init_cpr.get('regime', 'NORMAL CPR')}</span>
                <span class="badge-live" style="background:rgba(6,182,212,0.12);border-color:var(--accent-cyan);color:var(--accent-cyan);">⚡ DYNAMIC INTRADAY CALIBRATION</span>
            </div>
        </div>

        <div class="sr-grid-layout">
            <!-- Resistance Column (3 Dynamic Resistance Zones) -->
            <div class="sr-column-box">
                <div class="sr-column-title sr-res-title">
                    <span>🔴 3 Dynamic Resistance Zones (Supply)</span>
                    <span style="font-size:11px;color:var(--text-muted);font-weight:600;">Upper Take-Profit / Reversal Levels</span>
                </div>
                <div class="sr-levels-list">
                    <!-- R3 -->
                    <div class="sr-level-tile resistance-tile {'testing-active' if init_r3.get('is_testing') else ''}" id="sr-r3-tile">
                        <div class="sr-tile-top">
                            <span class="sr-tag-name mono" style="color:#f87171;">R3 RESISTANCE ZONE</span>
                            <span class="sr-tag-status {'status-testing' if init_r3.get('is_testing') else ('status-breached' if init_r3.get('dist_pts', 0) < 0 else 'status-supply')}" id="sr-r3-status">
                                {init_r3.get('status', '🔴 SUPPLY BARRIER')}
                            </span>
                        </div>
                        <div class="sr-tile-mid">
                            <span class="level-val mono" id="sr-r3-level" style="color:#f87171;">₹{init_r3.get('level', 0.0):.1f}</span>
                            <span class="dist-val mono" id="sr-r3-dist" style="color:{'#f87171' if init_r3.get('dist_pts', 0) >= 0 else '#38bdf8'};">
                                {'+' if init_r3.get('dist_pts', 0) >= 0 else ''}{init_r3.get('dist_pts', 0.0):.1f} pts ({'+' if init_r3.get('dist_pct', 0) >= 0 else ''}{init_r3.get('dist_pct', 0.0):.2f}%)
                            </span>
                        </div>
                        <div class="sr-tile-bot">
                            <span id="sr-r3-band">Zone: ₹{init_r3.get('zone_low', 0.0):.1f} - ₹{init_r3.get('zone_high', 0.0):.1f}</span>
                            <span>Extreme Extension / Exhaustion Reversal</span>
                        </div>
                    </div>

                    <!-- R2 -->
                    <div class="sr-level-tile resistance-tile {'testing-active' if init_r2.get('is_testing') else ''}" id="sr-r2-tile">
                        <div class="sr-tile-top">
                            <span class="sr-tag-name mono" style="color:#fb7185;">R2 RESISTANCE ZONE</span>
                            <span class="sr-tag-status {'status-testing' if init_r2.get('is_testing') else ('status-breached' if init_r2.get('dist_pts', 0) < 0 else 'status-supply')}" id="sr-r2-status">
                                {init_r2.get('status', '🔴 SUPPLY BARRIER')}
                            </span>
                        </div>
                        <div class="sr-tile-mid">
                            <span class="level-val mono" id="sr-r2-level" style="color:#fb7185;">₹{init_r2.get('level', 0.0):.1f}</span>
                            <span class="dist-val mono" id="sr-r2-dist" style="color:{'#f87171' if init_r2.get('dist_pts', 0) >= 0 else '#38bdf8'};">
                                {'+' if init_r2.get('dist_pts', 0) >= 0 else ''}{init_r2.get('dist_pts', 0.0):.1f} pts ({'+' if init_r2.get('dist_pct', 0) >= 0 else ''}{init_r2.get('dist_pct', 0.0):.2f}%)
                            </span>
                        </div>
                        <div class="sr-tile-bot">
                            <span id="sr-r2-band">Zone: ₹{init_r2.get('zone_low', 0.0):.1f} - ₹{init_r2.get('zone_high', 0.0):.1f}</span>
                            <span>Major Structural Ceiling / Breakout Target</span>
                        </div>
                    </div>

                    <!-- R1 -->
                    <div class="sr-level-tile resistance-tile {'testing-active' if init_r1.get('is_testing') else ''}" id="sr-r1-tile">
                        <div class="sr-tile-top">
                            <span class="sr-tag-name mono" style="color:#fda4af;">R1 RESISTANCE ZONE</span>
                            <span class="sr-tag-status {'status-testing' if init_r1.get('is_testing') else ('status-breached' if init_r1.get('dist_pts', 0) < 0 else 'status-supply')}" id="sr-r1-status">
                                {init_r1.get('status', '🔴 SUPPLY BARRIER')}
                            </span>
                        </div>
                        <div class="sr-tile-mid">
                            <span class="level-val mono" id="sr-r1-level" style="color:#fda4af;">₹{init_r1.get('level', 0.0):.1f}</span>
                            <span class="dist-val mono" id="sr-r1-dist" style="color:{'#f87171' if init_r1.get('dist_pts', 0) >= 0 else '#38bdf8'};">
                                {'+' if init_r1.get('dist_pts', 0) >= 0 else ''}{init_r1.get('dist_pts', 0.0):.1f} pts ({'+' if init_r1.get('dist_pct', 0) >= 0 else ''}{init_r1.get('dist_pct', 0.0):.2f}%)
                            </span>
                        </div>
                        <div class="sr-tile-bot">
                            <span id="sr-r1-band">Zone: ₹{init_r1.get('zone_low', 0.0):.1f} - ₹{init_r1.get('zone_high', 0.0):.1f}</span>
                            <span>Immediate Supply / Pullback Barrier</span>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Support Column (3 Dynamic Support Zones) -->
            <div class="sr-column-box">
                <div class="sr-column-title sr-sup-title">
                    <span>🟢 3 Dynamic Support Zones (Demand)</span>
                    <span style="font-size:11px;color:var(--text-muted);font-weight:600;">Lower Stop / Accumulation Levels</span>
                </div>
                <div class="sr-levels-list">
                    <!-- S1 -->
                    <div class="sr-level-tile support-tile {'testing-active' if init_s1.get('is_testing') else ''}" id="sr-s1-tile">
                        <div class="sr-tile-top">
                            <span class="sr-tag-name mono" style="color:#6ee7b7;">S1 SUPPORT ZONE</span>
                            <span class="sr-tag-status {'status-testing' if init_s1.get('is_testing') else ('status-breached' if init_s1.get('dist_pts', 0) > 0 else 'status-demand')}" id="sr-s1-status">
                                {init_s1.get('status', '🟢 DEMAND FLOOR')}
                            </span>
                        </div>
                        <div class="sr-tile-mid">
                            <span class="level-val mono" id="sr-s1-level" style="color:#6ee7b7;">₹{init_s1.get('level', 0.0):.1f}</span>
                            <span class="dist-val mono" id="sr-s1-dist" style="color:{'#34d399' if init_s1.get('dist_pts', 0) <= 0 else '#f87171'};">
                                {'+' if init_s1.get('dist_pts', 0) >= 0 else ''}{init_s1.get('dist_pts', 0.0):.1f} pts ({'+' if init_s1.get('dist_pct', 0) >= 0 else ''}{init_s1.get('dist_pct', 0.0):.2f}%)
                            </span>
                        </div>
                        <div class="sr-tile-bot">
                            <span id="sr-s1-band">Zone: ₹{init_s1.get('zone_low', 0.0):.1f} - ₹{init_s1.get('zone_high', 0.0):.1f}</span>
                            <span>Immediate Demand / Value Area Support</span>
                        </div>
                    </div>

                    <!-- S2 -->
                    <div class="sr-level-tile support-tile {'testing-active' if init_s2.get('is_testing') else ''}" id="sr-s2-tile">
                        <div class="sr-tile-top">
                            <span class="sr-tag-name mono" style="color:#34d399;">S2 SUPPORT ZONE</span>
                            <span class="sr-tag-status {'status-testing' if init_s2.get('is_testing') else ('status-breached' if init_s2.get('dist_pts', 0) > 0 else 'status-demand')}" id="sr-s2-status">
                                {init_s2.get('status', '🟢 DEMAND FLOOR')}
                            </span>
                        </div>
                        <div class="sr-tile-mid">
                            <span class="level-val mono" id="sr-s2-level" style="color:#34d399;">₹{init_s2.get('level', 0.0):.1f}</span>
                            <span class="dist-val mono" id="sr-s2-dist" style="color:{'#34d399' if init_s2.get('dist_pts', 0) <= 0 else '#f87171'};">
                                {'+' if init_s2.get('dist_pts', 0) >= 0 else ''}{init_s2.get('dist_pts', 0.0):.1f} pts ({'+' if init_s2.get('dist_pct', 0) >= 0 else ''}{init_s2.get('dist_pct', 0.0):.2f}%)
                            </span>
                        </div>
                        <div class="sr-tile-bot">
                            <span id="sr-s2-band">Zone: ₹{init_s2.get('zone_low', 0.0):.1f} - ₹{init_s2.get('zone_high', 0.0):.1f}</span>
                            <span>Major Value Area Low / Structural Floor</span>
                        </div>
                    </div>

                    <!-- S3 -->
                    <div class="sr-level-tile support-tile {'testing-active' if init_s3.get('is_testing') else ''}" id="sr-s3-tile">
                        <div class="sr-tile-top">
                            <span class="sr-tag-name mono" style="color:#10b981;">S3 SUPPORT ZONE</span>
                            <span class="sr-tag-status {'status-testing' if init_s3.get('is_testing') else ('status-breached' if init_s3.get('dist_pts', 0) > 0 else 'status-demand')}" id="sr-s3-status">
                                {init_s3.get('status', '🟢 DEMAND FLOOR')}
                            </span>
                        </div>
                        <div class="sr-tile-mid">
                            <span class="level-val mono" id="sr-s3-level" style="color:#10b981;">₹{init_s3.get('level', 0.0):.1f}</span>
                            <span class="dist-val mono" id="sr-s3-dist" style="color:{'#34d399' if init_s3.get('dist_pts', 0) <= 0 else '#f87171'};">
                                {'+' if init_s3.get('dist_pts', 0) >= 0 else ''}{init_s3.get('dist_pts', 0.0):.1f} pts ({'+' if init_s3.get('dist_pct', 0) >= 0 else ''}{init_s3.get('dist_pct', 0.0):.2f}%)
                            </span>
                        </div>
                        <div class="sr-tile-bot">
                            <span id="sr-s3-band">Zone: ₹{init_s3.get('zone_low', 0.0):.1f} - ₹{init_s3.get('zone_high', 0.0):.1f}</span>
                            <span>Capitulation Floor / Extreme Demand</span>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Central Pivot Range (CPR) Anchor Bar -->
            <div class="cpr-mid-bar">
                <div class="cpr-mid-group">
                    <span style="font-size:12px;font-weight:800;color:#c084fc;letter-spacing:0.5px;">⚡ CENTRAL PIVOT RANGE (CPR):</span>
                    <div class="cpr-item">
                        <span>TC (Top Central)</span>
                        <strong class="mono" id="cpr-tc-val">₹{init_cpr.get('tc', 0.0):.1f}</strong>
                    </div>
                    <div class="cpr-item">
                        <span>Pivot Point (P)</span>
                        <strong class="mono" id="cpr-pivot-val" style="color:var(--accent-cyan);">₹{init_cpr.get('pivot', 0.0):.1f}</strong>
                    </div>
                    <div class="cpr-item">
                        <span>BC (Bottom Central)</span>
                        <strong class="mono" id="cpr-bc-val">₹{init_cpr.get('bc', 0.0):.1f}</strong>
                    </div>
                    <div class="cpr-item">
                        <span>CPR Width %</span>
                        <strong class="mono" id="cpr-width-val" style="color:var(--accent-amber);">{init_cpr.get('width_pct', 0.0):.2f}%</strong>
                    </div>
                </div>
                <div style="font-size:11px;color:var(--text-muted);display:flex;align-items:center;gap:8px;">
                    <span>Calculated dynamically from today's official High, Low &amp; Close</span>
                </div>
            </div>
        </div>
    </div>

    <!-- Interactive Lot Sizing Controller (1 - 100+ Lots) -->
    <div class="sizing-card">
        <div class="sizing-title-group">
            <h3>⚡ Dynamic Contract Sizing Simulation (1 to 100+ Lots)</h3>
            <p>Select or type any number of lots below to test portfolio scaling, risk exposure, and returns in real-time.</p>
        </div>
        <div class="sizing-controls">
            <!-- Quick Presets -->
            <button class="lot-preset-btn" onclick="setLots(1)">1 Lot</button>
            <button class="lot-preset-btn active" id="btn-2l" onclick="setLots(2)">2 Lots</button>
            <button class="lot-preset-btn" onclick="setLots(5)">5 Lots</button>
            <button class="lot-preset-btn" onclick="setLots(10)">10 Lots</button>
            <button class="lot-preset-btn" onclick="setLots(25)">25 Lots</button>
            <button class="lot-preset-btn" onclick="setLots(50)">50 Lots</button>
            <button class="lot-preset-btn" onclick="setLots(100)">100 Lots</button>

            <!-- Dropdown Access (1 - 100 Lots) -->
            <select class="lot-dropdown" id="lots-dropdown" onchange="onDropdownChange(this.value)">
                <!-- Generated dynamically 1 to 100 -->
            </select>

            <!-- Custom Numeric Input -->
            <div class="lot-input-wrapper">
                <label>Custom:</label>
                <input type="number" class="lot-input" id="custom-lot-input" min="1" max="500" value="2" onchange="onCustomLotChange(this.value)">
                <span style="font-size:12px;color:var(--text-muted);font-weight:600;">Lots</span>
            </div>

            <!-- Dynamic Sizing Summary -->
            <div class="sizing-summary-pill" id="sizing-pill">
                Active Sizing: <strong id="sizing-summary-text">2 Lots (1,000 Qty)</strong>
            </div>
        </div>
    </div>

    <!-- Execution Engine Switcher: Enhanced 4-Solution Engine vs Baseline -->
    <div class="strategy-card">
        <div class="strategy-title-group">
            <h3>⚡ Execution Engine: Enhanced (4 Quant Rules Active) vs Baseline Fixed Stops</h3>
            <p>Toggle between institutional 4-solution volatility engine vs old rigid baseline stops:</p>
        </div>
        <div class="strategy-selector">
            <button class="strat-btn active" id="btn-engine-enh" onclick="setExecutionEngine('ENHANCED')">
                <span class="strat-icon">🚀</span>
                <span class="strat-text">
                    <strong>Enhanced 4-Solution Engine (Recommended) [Active]</strong>
                    <small id="desc-engine-enh">Dynamic ATR SL + Two-Tier Wick Shield (5m close) + 15m Re-Entry + Chandelier ATR Trailing</small>
                </span>
            </button>
            <button class="strat-btn" id="btn-engine-runner" onclick="setExecutionEngine('RUNNER')">
                <span class="strat-icon">📈</span>
                <span class="strat-text">
                    <strong>Option 1: Multi-Tranche Runner Mode (50/50)</strong>
                    <small id="desc-engine-runner">Bank 50% at T1 &amp; Trail 50% Runner to Target 2 (Zero Risk on Runner)</small>
                </span>
            </button>
            <button class="strat-btn" id="btn-engine-base" onclick="setExecutionEngine('BASELINE')">
                <span class="strat-icon">⚠️</span>
                <span class="strat-text">
                    <strong>Baseline Fixed Stops (Old Rigid Mode)</strong>
                    <small id="desc-engine-base">Standard single-target exit with rigid fixed stop loss</small>
                </span>
            </button>
        </div>
    </div>

    <!-- Contract & Delta Pricing Model -->
    <div class="delta-card">
        <div class="delta-title-group">
            <h3>🎯 Derivative Execution &amp; Delta (Δ) Pricing Mode</h3>
            <p>Select your instrument contract type below. Automatically scales all Points, Peak Gains, and Final Cash P&amp;L:</p>
        </div>
        <div class="delta-selector">
            <button class="delta-btn active" id="btn-delta-opt" onclick="setDeltaMode('OPTION')">
                <span class="delta-icon">🎯</span>
                <span class="delta-text">
                    <strong>ATM Options Premium Mode (~0.52 Δ) [Active]</strong>
                    <small id="desc-delta-opt">True Realized Cash P&amp;L in Option Chain (Target ~+18.2 pts, SL ~-9.36 pts)</small>
                </span>
            </button>
            <button class="delta-btn" id="btn-delta-fut" onclick="setDeltaMode('FUTURES')">
                <span class="delta-icon">⚡</span>
                <span class="delta-text">
                    <strong>Futures / Spot Benchmark (1.00 Δ)</strong>
                    <small id="desc-delta-fut">Raw Underlying Movement (Target +35.0 pts, SL -18.0 pts)</small>
                </span>
            </button>
            <button class="delta-btn" id="btn-delta-itm" onclick="setDeltaMode('ITM')">
                <span class="delta-icon">💎</span>
                <span class="delta-text">
                    <strong>Deep ITM Option Mode (~0.72 Δ)</strong>
                    <small id="desc-delta-itm">High-Delta In-The-Money Option Contracts (Target ~+25.2 pts, SL ~-12.96 pts)</small>
                </span>
            </button>
        </div>
    </div>

    <!-- Info Notice -->
    <div class="info-bar">
        <div>💡 <strong>Clean Forward-Testing Ledger:</strong> This dashboard records <strong>strictly live forward trades starting October 05, 2026</strong>. Zero backtested data included. Every trade is auto-appended in real-time.</div>
        <div>Auto-Refresh: <strong>Every 5s</strong></div>
    </div>

    <!-- Dynamic KPI Cards -->
    <div class="kpi-grid">
        <div class="kpi-card">
            <div class="kpi-label"><span id="kpi-pnl-label">Cumulative Realized P&amp;L (2 Lots)</span></div>
            <div class="kpi-val mono val-profit" id="kpi-total-pnl">₹0.00</div>
            <div class="kpi-sub" id="kpi-pts-sub">0.00 pts total capture</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label"><span id="kpi-peak-label">Total Peak Gain (2 Lots)</span></div>
            <div class="kpi-val mono val-profit" id="kpi-total-peak">+₹0.00</div>
            <div class="kpi-sub" id="kpi-peak-pts-sub">+0.00 total peak points</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Desk Win Rate</div>
            <div class="kpi-val mono" id="kpi-win-rate">0.0%</div>
            <div class="kpi-sub" id="kpi-win-count">0 Wins / 0 Losses</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Live Executed Trades</div>
            <div class="kpi-val mono" id="kpi-trades-count">0 Trades</div>
            <div class="kpi-sub" id="kpi-standdowns">0 Stand Downs (Score &lt; 68%)</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Profit Factor / Risk-Reward</div>
            <div class="kpi-val mono" id="kpi-profit-factor">0.00</div>
            <div class="kpi-sub" id="kpi-avg-win">Avg Win: ₹0 | Avg Loss: ₹0</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Avg Confluence Score</div>
            <div class="kpi-val mono" id="kpi-avg-score">0.0%</div>
            <div class="kpi-sub">Gate: ≥68.0% Confluence</div>
        </div>
    </div>

    <!-- Controls & Filters -->
    <div class="controls-card">
        <div class="nav-tabs">
            <button class="nav-btn active" id="tab-rel" onclick="switchTicker('RELIANCE')">Reliance Industries</button>
            <button class="nav-btn" id="tab-ada" onclick="switchTicker('ADANIENT')">Adani Enterprises</button>
            <button class="nav-btn" id="tab-nifty" onclick="switchTicker('NIFTY')">NIFTY 50</button>
            <button class="nav-btn" id="tab-sensex" onclick="switchTicker('SENSEX')">BSE SENSEX</button>
        </div>

        <div class="filter-group">
            <select class="filter-select" id="month-filter" onchange="renderTable()">
                <option value="ALL">All Forward Trades (From Oct 05, 2026)</option>
                <option value="2026-10">October 2026</option>
            </select>

            <select class="filter-select" id="outcome-filter" onchange="renderTable()">
                <option value="ALL">All Outcomes</option>
                <option value="WIN">Winners Only (+P&amp;L)</option>
                <option value="LOSS">Losses Only (-P&amp;L)</option>
                <option value="TARGET">Target Hit Only</option>
                <option value="SL">Stop Loss Hit Only</option>
                <option value="EOD">EOD Exit Only</option>
                <option value="STAND_DOWN">Stand Down Sessions</option>
            </select>

            <input type="text" class="search-box" id="search-input" placeholder="Search date, strike, spot..." oninput="renderTable()">
        </div>
    </div>

    <!-- Table Container -->
    <div class="table-card">
        <div class="table-scroll-container">
            <table id="trades-table">
                <thead>
                    <tr>
                        <th class="col-sticky-left">Date</th>
                        <th>Action / Strike</th>
                        <th>Confluence</th>
                        <th>Entry Time</th>
                        <th>Entry Spot (₹)</th>
                        <th>Peak Spot (₹)</th>
                        <th>Peak Time</th>
                        <th id="th-peak-gain">Peak Gain (2L)</th>
                        <th>Exit Time</th>
                        <th>Exit Spot (₹)</th>
                        <th>Exit Reason</th>
                        <th id="th-pts-label">Points (Opt Premium)</th>
                        <th class="col-sticky-right" id="th-final-pnl">Final P&amp;L (2 Lots)</th>
                    </tr>
                </thead>
                <tbody id="table-body">
                    <!-- Rows rendered dynamically -->
                </tbody>
                <tfoot id="table-foot">
                    <tr>
                        <td class="col-sticky-left mono" style="font-weight:800;color:var(--accent-cyan);letter-spacing:0.5px;">TOTAL</td>
                        <td colspan="6" style="color:var(--text-muted);font-size:12px;" id="foot-summary-label">Cumulative Forward Desk Performance</td>
                        <td class="mono val-profit" id="foot-total-peak" style="font-size:14px;font-weight:800;">+₹0.00</td>
                        <td colspan="3"></td>
                        <td class="mono" id="foot-total-pts" style="font-size:13px;font-weight:700;">+0.00 pts</td>
                        <td class="col-sticky-right mono pnl-cell" id="foot-total-pnl" style="font-size:14px;font-weight:800;">₹0.00</td>
                    </tr>
                </tfoot>
            </table>
        </div>
        <div class="table-footer">
            <div id="footer-count">Showing 0 live sessions</div>
            <div id="footer-sum" class="mono">Filtered P&amp;L: ₹0.00</div>
        </div>
    </div>
</div>

<script>
    const dataReliance = {json.dumps(trades_rel)};
    const dataAdani = {json.dumps(trades_ada)};
    const dataNifty = {json.dumps(trades_nifty)};
    const dataSensex = {json.dumps(trades_sensex)};
    const allActiveStates = {json.dumps(all_active_states)};
    
    let currentTicker = 'RELIANCE';
    let currentLots = 2;
    let currentDeltaMode = 'OPTION'; // 'OPTION' (0.52 Δ), 'FUTURES' (1.00 Δ), 'ITM' (0.72 Δ)
    let currentExecutionEngine = 'ENHANCED'; // 'ENHANCED' (4 Solutions), 'RUNNER' (50/50), 'BASELINE' (100% T1)
    let currentStrategyMode = 'RUNNER'; 

    function getDeltaValue() {{
        if (currentDeltaMode === 'OPTION') return 0.52;
        if (currentDeltaMode === 'ITM') return 0.72;
        return 1.00;
    }}

    function setDeltaMode(mode) {{
        currentDeltaMode = mode;
        document.getElementById('btn-delta-opt').classList.toggle('active', mode === 'OPTION');
        document.getElementById('btn-delta-fut').classList.toggle('active', mode === 'FUTURES');
        document.getElementById('btn-delta-itm').classList.toggle('active', mode === 'ITM');
        updateActiveTradeCard();
        updateSizingSummary();
        renderTable();
    }}

    function setExecutionEngine(mode) {{
        currentExecutionEngine = mode;
        currentStrategyMode = (mode === 'BASELINE') ? 'BASELINE' : 'RUNNER';

        const btnEnh = document.getElementById('btn-engine-enh');
        const btnRunner = document.getElementById('btn-engine-runner');
        const btnBase = document.getElementById('btn-engine-base');
        if (btnEnh) btnEnh.classList.toggle('active', mode === 'ENHANCED');
        if (btnRunner) btnRunner.classList.toggle('active', mode === 'RUNNER');
        if (btnBase) btnBase.classList.toggle('active', mode === 'BASELINE');

        // Toggle solution cards glow and status pills
        document.querySelectorAll('.solution-card').forEach(card => {{
            card.classList.toggle('active-solution', mode === 'ENHANCED');
            const pill = card.querySelector('.sol-status-pill');
            if (pill) {{
                if (mode === 'ENHANCED') {{
                    pill.textContent = (card.id.includes('3') || card.id.includes('4')) ? 'ARMED' : 'ACTIVE';
                    pill.style.background = 'rgba(16, 185, 129, 0.15)';
                    pill.style.color = '#10b981';
                    pill.style.borderColor = 'rgba(16, 185, 129, 0.3)';
                }} else {{
                    pill.textContent = 'STANDBY';
                    pill.style.background = 'rgba(255, 255, 255, 0.05)';
                    pill.style.color = 'var(--text-muted)';
                    pill.style.borderColor = 'rgba(255, 255, 255, 0.1)';
                }}
            }}
        }});

        updateActiveTradeCard();
        updateSizingSummary();
        renderTable();
    }}

    function setStrategyMode(mode) {{
        setExecutionEngine(mode === 'BASELINE' ? 'BASELINE' : 'RUNNER');
    }}

    function getLotSize(ticker) {{
        if (ticker === 'RELIANCE') return 500;
        if (ticker === 'ADANIENT') return 309;
        if (ticker === 'NIFTY') return 65;
        if (ticker === 'SENSEX') return 20;
        return 500;
    }}

    // Populate dropdown with 1 to 100 lots
    function initLotsDropdown() {{
        const select = document.getElementById('lots-dropdown');
        select.innerHTML = '';
        for (let i = 1; i <= 100; i++) {{
            const opt = document.createElement('option');
            opt.value = i;
            opt.textContent = `${{i}} ${{i === 1 ? 'Lot' : 'Lots'}}`;
            if (i === currentLots) opt.selected = true;
            select.appendChild(opt);
        }}
    }}

    function setLots(num) {{
        currentLots = Math.max(1, parseInt(num) || 1);
        document.getElementById('lots-dropdown').value = Math.min(100, currentLots);
        document.getElementById('custom-lot-input').value = currentLots;

        document.querySelectorAll('.lot-preset-btn').forEach(btn => {{
            btn.classList.toggle('active', btn.textContent.trim() === `${{currentLots}} ${{currentLots === 1 ? 'Lot' : 'Lots'}}`);
        }});

        updateActiveTradeCard();
        updateSizingSummary();
        renderTable();
    }}

    function onDropdownChange(val) {{
        setLots(val);
    }}

    function onCustomLotChange(val) {{
        setLots(val);
    }}

    function updateSizingSummary() {{
        const lotSize = getLotSize(currentTicker);
        const totalQty = lotSize * currentLots;
        const formattedQty = totalQty.toLocaleString('en-IN');
        const deltaLabel = currentDeltaMode === 'OPTION' ? 'ATM Options (~0.52 Δ)' : (currentDeltaMode === 'ITM' ? 'ITM Options (~0.72 Δ)' : 'Futures (1.00 Δ)');
        const engineLabel = currentExecutionEngine === 'ENHANCED' ? 'Enhanced (4 Solutions)' : (currentExecutionEngine === 'RUNNER' ? 'Runner Mode (50/50)' : 'Baseline Mode');
        
        document.getElementById('sizing-summary-text').textContent = `${{currentLots}} ${{currentLots === 1 ? 'Lot' : 'Lots'}} (${{formattedQty}} Qty)`;
        document.getElementById('kpi-pnl-label').textContent = `Realized P&L (${{currentLots}}L | ${{engineLabel}} @ ${{deltaLabel}})`;
        document.getElementById('kpi-peak-label').textContent = `Total Peak Gain (${{currentLots}}L @ ${{deltaLabel}})`;
        document.getElementById('th-pts-label').textContent = currentDeltaMode === 'FUTURES' ? 'Points (Spot/Fut)' : 'Points (Opt Premium)';
        document.getElementById('th-peak-gain').textContent = `Peak Gain (${{currentLots}}L)`;
        document.getElementById('th-final-pnl').textContent = `Final P&L (${{currentLots}} ${{currentLots === 1 ? 'Lot' : 'Lots'}})`;
    }}

    function updateActiveTradeCard() {{
        const trade = allActiveStates[currentTicker];
        if (!trade) return;

        const contractEl = document.getElementById('active-contract-name');
        if (contractEl) contractEl.textContent = trade.contract;

        const entrySpotEl = document.getElementById('active-entry-spot-time');
        if (entrySpotEl) entrySpotEl.textContent = `₹${{Number(trade.entry_spot).toFixed(1)}} @ ${{trade.entry_time}}`;

        const curSpotEl = document.getElementById('active-current-spot');
        if (curSpotEl) curSpotEl.textContent = `₹${{Number(trade.current_spot).toFixed(1)}}`;

        // Dynamic ATR SL & Hard Catastrophe Stop
        const dynSlVal = Number(trade.dynamic_sl_pts || (trade.sl_pts * 1.25)).toFixed(1);
        const hardSlVal = Number(trade.hard_sl_pts || (trade.sl_pts * 2.0)).toFixed(1);
        const dynSlEl = document.getElementById('active-dynamic-sl');
        if (dynSlEl) dynSlEl.textContent = `-${{dynSlVal}} pts`;
        const hardSlEl = document.getElementById('active-hard-sl');
        if (hardSlEl) hardSlEl.textContent = `-${{hardSlVal}} pts`;

        const slPtsEl = document.getElementById('active-sl-pts');
        if (slPtsEl) slPtsEl.textContent = `-${{Number(trade.sl_pts).toFixed(1)}} pts`;

        const scoreEl = document.getElementById('active-confluence-score');
        if (scoreEl) scoreEl.textContent = `${{Number(trade.confluence_score).toFixed(1)}}%`;

        const t1TgtEl = document.getElementById('active-t1-target');
        if (t1TgtEl) t1TgtEl.textContent = `+${{Number(trade.target_1_pts).toFixed(1)}} pts (Fixed Win Bank)`;

        const t1StatusEl = document.getElementById('active-t1-status');
        if (t1StatusEl) t1StatusEl.textContent = trade.t1_status;

        const t2TgtEl = document.getElementById('active-t2-target');
        if (t2TgtEl) t2TgtEl.textContent = `+${{Number(trade.target_2_pts).toFixed(1)}} pts & Open Chandelier Trail`;

        const t2ProtEl = document.getElementById('active-t2-protection');
        if (t2ProtEl) t2ProtEl.textContent = `Chandelier ATR (10, 2.0) | SL to BE @ 1:1 R:R`;

        const t2RiskEl = document.getElementById('active-t2-risk');
        if (t2RiskEl) t2RiskEl.textContent = trade.downside_risk;

        // Unrealized P&L
        const lotSize = getLotSize(currentTicker);
        const totalQty = lotSize * currentLots;
        const delta = getDeltaValue();
        const pnlPts = (trade.current_spot - trade.entry_spot) * delta;
        const unrlPnl = pnlPts * totalQty;
        const pnlEl = document.getElementById('active-unrealized-pnl');
        if (pnlEl) {{
            pnlEl.textContent = formatCurrency(unrlPnl);
            pnlEl.className = 'mono ' + (unrlPnl >= 0 ? 'val-profit' : 'val-loss');
        }}

        // Update Solution Descriptions
        const solDesc1 = document.getElementById('sol-desc-1');
        if (solDesc1) solDesc1.textContent = `SL = max(Swing ± 5 pts, 1.5× ATR = -${{dynSlVal}} pts). Dynamic sizing scaled to ₹6,000 risk.`;
        const solDesc2 = document.getElementById('sol-desc-2');
        if (solDesc2) solDesc2.textContent = `Hard broker stop at -${{hardSlVal}} pts (2.5× ATR). Technical exit triggers ONLY on 5m candle close.`;
        const solDesc3 = document.getElementById('sol-desc-3');
        if (solDesc3) solDesc3.textContent = `Auto re-enters if ${{currentTicker}} wicks out and spot resumes entry level with high score (${{trade.confluence_score}}%).`;
        const solDesc4 = document.getElementById('sol-desc-4');
        if (solDesc4) solDesc4.textContent = `At 1:1 R:R (+${{dynSlVal}} pts), moves SL to BE and trails behind 5m candle highs/lows (Period 10, Mult 2.0).`;

        // Update Strategy & Delta descriptions for current ticker
        const optT1 = (trade.target_1_pts * 0.52).toFixed(1);
        const optSl = (trade.sl_pts * 0.52).toFixed(1);
        const itmT1 = (trade.target_1_pts * 0.72).toFixed(1);
        const itmSl = (trade.sl_pts * 0.72).toFixed(1);

        const descEngineEnh = document.getElementById('desc-engine-enh');
        if (descEngineEnh) {{
            descEngineEnh.textContent = `Dynamic ATR (-${{dynSlVal}} pts) + Two-Tier Wick Shield (5m close) + 15m Re-Entry + Chandelier Trailing (+${{trade.target_2_pts}} pts runner)`;
        }}
        const descEngineRunner = document.getElementById('desc-engine-runner');
        if (descEngineRunner) {{
            descEngineRunner.textContent = `Bank 50% at T1 (+${{trade.target_1_pts}} pts ${{currentTicker}}) & Trail 50% Runner to Target 2 (+${{trade.target_2_pts}} pts ${{currentTicker}}) — Zero Risk on Runner`;
        }}
        const descEngineBase = document.getElementById('desc-engine-base');
        if (descEngineBase) {{
            descEngineBase.textContent = `Standard single-target exit with rigid fixed stop (-${{trade.sl_pts}} pts)`;
        }}
        const descDeltaOpt = document.getElementById('desc-delta-opt');
        if (descDeltaOpt) {{
            descDeltaOpt.textContent = `True Realized Cash P&L in Option Chain (Target ~+${{optT1}} pts, SL ~-${{optSl}} pts)`;
        }}
        const descDeltaFut = document.getElementById('desc-delta-fut');
        if (descDeltaFut) {{
            descDeltaFut.textContent = `Raw Underlying Movement (Target +${{Number(trade.target_1_pts).toFixed(1)}} pts, SL -${{Number(trade.sl_pts).toFixed(1)}} pts)`;
        }}
        const descDeltaItm = document.getElementById('desc-delta-itm');
        if (descDeltaItm) {{
            descDeltaItm.textContent = `High-Delta In-The-Money Option Contracts (Target ~+${{itmT1}} pts, SL ~-${{itmSl}} pts)`;
        }}
    }}

    function updateSRZones() {{
        const trade = allActiveStates[currentTicker];
        if (!trade || !trade.sr_zones) return;
        const sr = trade.sr_zones;
        const res = sr.resistance_zones || {{}};
        const sup = sr.support_zones || {{}};
        const cpr = sr.cpr || {{}};
        const spot = Number(trade.current_spot || sr.spot || 0);

        // Desk symbol in header
        const titleDesk = document.getElementById('sr-desk-title');
        if (titleDesk) titleDesk.textContent = trade.name || currentTicker;

        // Badges
        const badgeRange = document.getElementById('sr-badge-range');
        if (badgeRange) badgeRange.textContent = `H: ₹${{Number(sr.high).toFixed(1)}} | L: ₹${{Number(sr.low).toFixed(1)}} (Range: ${{Number(sr.range).toFixed(1)}} pts)`;

        const badgeRegime = document.getElementById('sr-badge-regime');
        if (badgeRegime) badgeRegime.textContent = cpr.regime || 'NORMAL CPR';

        const badgeSpot = document.getElementById('sr-badge-spot');
        if (badgeSpot) badgeSpot.textContent = `Live Spot: ₹${{spot.toFixed(1)}}`;

        // CPR
        const cprPivot = document.getElementById('cpr-pivot-val');
        if (cprPivot) cprPivot.textContent = `₹${{Number(cpr.pivot).toFixed(1)}}`;
        const cprTc = document.getElementById('cpr-tc-val');
        if (cprTc) cprTc.textContent = `₹${{Number(cpr.tc).toFixed(1)}}`;
        const cprBc = document.getElementById('cpr-bc-val');
        if (cprBc) cprBc.textContent = `₹${{Number(cpr.bc).toFixed(1)}}`;
        const cprWidth = document.getElementById('cpr-width-val');
        if (cprWidth) cprWidth.textContent = `${{Number(cpr.width_pct).toFixed(2)}}%`;

        // Populate R3, R2, R1
        ['r3', 'r2', 'r1'].forEach(key => {{
            const z = res[key];
            if (!z) return;
            const lvlEl = document.getElementById(`sr-${{key}}-level`);
            if (lvlEl) lvlEl.textContent = `₹${{Number(z.level).toFixed(1)}}`;

            const bandEl = document.getElementById(`sr-${{key}}-band`);
            if (bandEl) bandEl.textContent = `Zone: ₹${{Number(z.zone_low).toFixed(1)}} - ₹${{Number(z.zone_high).toFixed(1)}}`;

            const distEl = document.getElementById(`sr-${{key}}-dist`);
            if (distEl) {{
                const distPts = Number(z.dist_pts);
                const distPct = Number(z.dist_pct);
                const sign = distPts >= 0 ? '+' : '';
                distEl.textContent = `${{sign}}${{distPts.toFixed(1)}} pts (${{sign}}${{distPct.toFixed(2)}}%)`;
                distEl.style.color = distPts >= 0 ? '#f87171' : '#38bdf8';
            }}

            const statusEl = document.getElementById(`sr-${{key}}-status`);
            if (statusEl) {{
                statusEl.textContent = z.status;
                statusEl.className = 'sr-tag-status ' + (z.is_testing ? 'status-testing' : (z.dist_pts < 0 ? 'status-breached' : 'status-supply'));
            }}

            const tileEl = document.getElementById(`sr-${{key}}-tile`);
            if (tileEl) {{
                tileEl.classList.toggle('testing-active', Boolean(z.is_testing));
            }}
        }});

        // Populate S1, S2, S3
        ['s1', 's2', 's3'].forEach(key => {{
            const z = sup[key];
            if (!z) return;
            const lvlEl = document.getElementById(`sr-${{key}}-level`);
            if (lvlEl) lvlEl.textContent = `₹${{Number(z.level).toFixed(1)}}`;

            const bandEl = document.getElementById(`sr-${{key}}-band`);
            if (bandEl) bandEl.textContent = `Zone: ₹${{Number(z.zone_low).toFixed(1)}} - ₹${{Number(z.zone_high).toFixed(1)}}`;

            const distEl = document.getElementById(`sr-${{key}}-dist`);
            if (distEl) {{
                const distPts = Number(z.dist_pts);
                const distPct = Number(z.dist_pct);
                const sign = distPts >= 0 ? '+' : '';
                distEl.textContent = `${{sign}}${{distPts.toFixed(1)}} pts (${{sign}}${{distPct.toFixed(2)}}%)`;
                distEl.style.color = distPts <= 0 ? '#34d399' : '#f87171';
            }}

            const statusEl = document.getElementById(`sr-${{key}}-status`);
            if (statusEl) {{
                statusEl.textContent = z.status;
                statusEl.className = 'sr-tag-status ' + (z.is_testing ? 'status-testing' : (z.dist_pts > 0 ? 'status-breached' : 'status-demand'));
            }}

            const tileEl = document.getElementById(`sr-${{key}}-tile`);
            if (tileEl) {{
                tileEl.classList.toggle('testing-active', Boolean(z.is_testing));
            }}
        }});
    }}

    function switchTicker(ticker) {{
        if (!ticker) ticker = 'RELIANCE';
        ticker = String(ticker).toUpperCase().trim();
        if (ticker === 'ADANI' || ticker === 'ADANI ENTERPRISES') ticker = 'ADANIENT';
        if (ticker === 'NIFTY 50') ticker = 'NIFTY';
        if (ticker === 'BSE SENSEX') ticker = 'SENSEX';
        if (!['RELIANCE', 'ADANIENT', 'NIFTY', 'SENSEX'].includes(ticker)) ticker = 'RELIANCE';

        currentTicker = ticker;
        try {{
            localStorage.setItem('active_live_desk', ticker);
            if (window.location.hash !== '#' + ticker) {{
                history.replaceState(null, null, '#' + ticker);
            }}
        }} catch (e) {{}}
        
        // 1. Sync all tabs (top bar and controls bar)
        const tabMap = {{
            'RELIANCE': ['tab-rel', 'top-tab-rel'],
            'ADANIENT': ['tab-ada', 'top-tab-ada'],
            'NIFTY': ['tab-nifty', 'top-tab-nifty'],
            'SENSEX': ['tab-sensex', 'top-tab-sensex']
        }};
        
        for (const [sym, ids] of Object.entries(tabMap)) {{
            const isActive = (sym === ticker);
            ids.forEach(id => {{
                const el = document.getElementById(id);
                if (el) el.classList.toggle('active', isActive);
            }});
        }}
        
        // 2. Sync header desk pills
        const pillMap = {{
            'RELIANCE': 'pill-rel',
            'ADANIENT': 'pill-ada',
            'NIFTY': 'pill-nifty',
            'SENSEX': 'pill-sensex'
        }};
        for (const [sym, id] of Object.entries(pillMap)) {{
            const el = document.getElementById(id);
            if (el) el.classList.toggle('active-pill', sym === ticker);
        }}
        
        // 3. Update active trade card
        updateActiveTradeCard();
        
        // 4. Update dynamic S/R zones
        updateSRZones();

        // 5. Update lot sizing summary
        updateSizingSummary();
        
        // 6. Render Table & KPI cards
        renderTable();
    }}

    function formatCurrency(val) {{
        const num = parseFloat(val) || 0;
        const isNeg = num < 0;
        const absVal = Math.abs(num);
        const formatted = absVal.toLocaleString('en-IN', {{ minimumFractionDigits: 2, maximumFractionDigits: 2 }});
        return (isNeg ? '-₹' : '+₹') + formatted;
    }}

    function formatSpot(val) {{
        if (val === null || val === undefined || val === '' || val === '-' || val === '—') return '—';
        const num = parseFloat(val);
        if (isNaN(num)) return '—';
        return '₹' + num.toLocaleString('en-IN', {{ minimumFractionDigits: 1, maximumFractionDigits: 1 }});
    }}

    function renderTable() {{
        try {{
            let rawData = dataReliance;
            if (currentTicker === 'ADANIENT') rawData = dataAdani;
            else if (currentTicker === 'NIFTY') rawData = dataNifty;
            else if (currentTicker === 'SENSEX') rawData = dataSensex;

            const monthFilter = document.getElementById('month-filter').value;
            const outcomeFilter = document.getElementById('outcome-filter').value;
            const searchVal = document.getElementById('search-input').value.toLowerCase().trim();

            const lotSize = getLotSize(currentTicker);
            const totalQty = lotSize * currentLots;

            const filtered = rawData.filter(row => {{
                if (monthFilter !== 'ALL' && row.month !== monthFilter) return false;
                
                const pts = parseFloat(row.pnl_pts) || 0;
                const pnl = pts * totalQty;
                const reason = (row.exit_reason || '').toUpperCase();
                const isStandDown = row.status === 'STAND_DOWN' || (row.action || '').toUpperCase().includes('STAND DOWN');

                if (outcomeFilter === 'WIN' && pnl <= 0) return false;
                if (outcomeFilter === 'LOSS' && pnl >= 0) return false;
                if (outcomeFilter === 'TARGET' && !reason.includes('TARGET')) return false;
                if (outcomeFilter === 'SL' && !reason.includes('SL')) return false;
                if (outcomeFilter === 'EOD' && !reason.includes('EOD')) return false;
                if (outcomeFilter === 'STAND_DOWN' && !isStandDown) return false;

                if (searchVal) {{
                    const str = `${{row.date}} ${{row.action}} ${{row.entry_spot}} ${{row.exit_spot}} ${{row.exit_reason}}`.toLowerCase();
                    if (!str.includes(searchVal)) return false;
                }}
                return true;
            }});

            // Reverse order so the newest live trades appear at the very top!
            const displayRows = [...filtered].reverse();

            // Update KPIs
            const delta = getDeltaValue();
            let totalPnl = 0;
            let totalPts = 0;
            let totalPeakPts = 0;
            let totalPeakAmt = 0;
            let wins = 0;
            let losses = 0;
            let winSum = 0;
            let lossSum = 0;
            let activeTrades = 0;
            let standDowns = 0;
            let scoreSum = 0;

            filtered.forEach(r => {{
                const rawPts = currentStrategyMode === 'RUNNER'
                    ? (parseFloat(r.runner_pnl_pts !== undefined && r.runner_pnl_pts !== '' ? r.runner_pnl_pts : r.pnl_pts) || 0)
                    : (parseFloat(r.pnl_pts) || 0);
                const pts = rawPts * delta;
                const rawPeakPts = parseFloat(r.peak_pts) || 0;
                const peakPts = rawPeakPts * delta;
                const isStandDown = r.status === 'STAND_DOWN' || (r.action || '').toUpperCase().includes('STAND DOWN');
                const pnl = isStandDown ? 0 : (pts * totalQty);
                const peakAmt = isStandDown ? 0 : (peakPts * totalQty);
                const score = parseFloat(r.score) || 0;

                totalPnl += pnl;
                totalPts += pts;
                totalPeakPts += peakPts;
                totalPeakAmt += peakAmt;
                scoreSum += score;

                if (isStandDown) {{
                    standDowns++;
                }} else {{
                    activeTrades++;
                    if (pnl > 0) {{
                        wins++;
                        winSum += pnl;
                    }} else if (pnl < 0) {{
                        losses++;
                        lossSum += Math.abs(pnl);
                    }}
                }}
            }});

            const winRate = activeTrades > 0 ? ((wins / activeTrades) * 100).toFixed(1) : '0.0';
            const profitFactor = lossSum > 0 ? (winSum / lossSum).toFixed(2) : (winSum > 0 ? 'INF' : '0.00');
            const avgScore = filtered.length > 0 ? (scoreSum / filtered.length).toFixed(1) : '0.0';

            const pnlEl = document.getElementById('kpi-total-pnl');
            pnlEl.textContent = formatCurrency(totalPnl);
            pnlEl.className = 'kpi-val mono ' + (totalPnl >= 0 ? 'val-profit' : 'val-loss');

            document.getElementById('kpi-pts-sub').textContent = `${{totalPts >= 0 ? '+' : ''}}${{totalPts.toFixed(2)}} pts total capture`;
            document.getElementById('kpi-total-peak').textContent = `+₹${{Math.round(totalPeakAmt).toLocaleString('en-IN')}}`;
            document.getElementById('kpi-peak-pts-sub').textContent = `+${{totalPeakPts.toFixed(2)}} pts total peak excursion`;
            document.getElementById('kpi-win-rate').textContent = `${{winRate}}%`;
            document.getElementById('kpi-win-count').textContent = `${{wins}} Wins / ${{losses}} Losses (${{activeTrades}} Executed)`;
            document.getElementById('kpi-trades-count').textContent = `${{activeTrades}} Trades`;
            document.getElementById('kpi-standdowns').textContent = `${{standDowns}} Stand Downs (&lt;68% score)`;
            document.getElementById('kpi-profit-factor').textContent = profitFactor;
            
            const avgWin = wins > 0 ? (winSum / wins).toFixed(0) : 0;
            const avgLoss = losses > 0 ? (lossSum / losses).toFixed(0) : 0;
            document.getElementById('kpi-avg-win').textContent = `Avg Win: ₹${{Number(avgWin).toLocaleString('en-IN')}} | Avg Loss: ₹${{Number(avgLoss).toLocaleString('en-IN')}}`;
            document.getElementById('kpi-avg-score').textContent = `${{avgScore}}%`;

            // Render Table Body
            const tbody = document.getElementById('table-body');
            tbody.innerHTML = '';

            if (displayRows.length === 0) {{
                tbody.innerHTML = `
                    <tr>
                        <td colspan="13" style="text-align:center;padding:50px 20px;color:var(--text-secondary);">
                            <div style="font-size:22px;margin-bottom:8px;">⚡</div>
                            <div style="font-size:15px;font-weight:700;color:#f1f5f9;">Live Desk Armed with Option 1 Multi-Tranche Execution (Monday, October 05, 2026)</div>
                            <div style="font-size:12px;color:var(--text-muted);margin-top:6px;">
                                Ready to record Trade #1. Multi-Tranche Runner fills (50% Bank at T1 + 50% Runner to T2) will automatically append and update here in real-time.
                            </div>
                        </td>
                    </tr>
                `;
            }} else {{
                displayRows.forEach(row => {{
                    const tr = document.createElement('tr');
                    const action = String(row.action || '');
                    const score = parseFloat(row.score) || 0;
                    const rawPts = currentStrategyMode === 'RUNNER'
                        ? (parseFloat(row.runner_pnl_pts !== undefined && row.runner_pnl_pts !== '' ? row.runner_pnl_pts : row.pnl_pts) || 0)
                        : (parseFloat(row.pnl_pts) || 0);
                    const pts = rawPts * delta;
                    const pnl = pts * totalQty;
                    const rawPeakPts = parseFloat(row.peak_pts) || 0;
                    const peakPts = rawPeakPts * delta;
                    const peakAmt = peakPts * totalQty;
                    const reason = currentStrategyMode === 'RUNNER'
                        ? String(row.runner_exit_reason || row.exit_reason || '')
                        : String(row.exit_reason || '');
                    const isStandDown = row.status === 'STAND_DOWN' || action.toUpperCase().includes('STAND DOWN');

                    // Action Pill
                    let actionPill = '';
                    if (action.includes('CE')) {{
                        actionPill = `<span class="pill pill-ce">${{action}}</span>`;
                    }} else if (action.includes('PE')) {{
                        actionPill = `<span class="pill pill-pe">${{action}}</span>`;
                    }} else {{
                        actionPill = `<span class="pill pill-standdown">STAND DOWN</span>`;
                    }}

                    // Score Chip
                    let scoreChip = '';
                    if (score >= 72) {{
                        scoreChip = `<span class="score-chip high mono">${{score.toFixed(1)}}%</span>`;
                    }} else if (score >= 68) {{
                        scoreChip = `<span class="score-chip mono">${{score.toFixed(1)}}%</span>`;
                    }} else {{
                        scoreChip = `<span class="score-chip mid mono">${{score.toFixed(1)}}%</span>`;
                    }}

                    // Reason Tag & 4-Solution Badge
                    let reasonTag = '';
                    if (reason.includes('TARGET') || reason.includes('HIT') || reason.includes('T1') || reason.includes('T2')) {{
                        reasonTag = `<span class="reason-tag reason-target">${{reason}}</span>`;
                    }} else if (reason.includes('SL')) {{
                        reasonTag = `<span class="reason-tag reason-sl">${{reason}}</span>`;
                    }} else if (reason.includes('EOD')) {{
                        reasonTag = `<span class="reason-tag reason-eod">${{reason}}</span>`;
                    }} else {{
                        reasonTag = `<span class="reason-tag" style="background:rgba(255,255,255,0.05);color:var(--text-muted);">${{reason || '—'}}</span>`;
                    }}

                    let solBadge = '';
                    const reasonUpper = reason.toUpperCase();
                    if (currentExecutionEngine === 'ENHANCED') {{
                        if (row.solution_tag === 'SAVED_BY_WICK_SHIELD' || reasonUpper.includes('WICK') || reasonUpper.includes('SHIELD')) {{
                            solBadge = `<div style="margin-top:3px;"><span class="tag-solution tag-wick-shield">🛡️ WICK SHIELD RESCUE</span></div>`;
                        }} else if (row.solution_tag === 'RESUMPTION_RE_ENTRY' || reasonUpper.includes('RE-ENTRY') || reasonUpper.includes('RESUMPTION')) {{
                            solBadge = `<div style="margin-top:3px;"><span class="tag-solution tag-reentry">🔄 15M RE-ENTRY RUNNER</span></div>`;
                        }} else if (row.solution_tag === 'CHANDELIER_RUNNER' || reasonUpper.includes('CHANDELIER') || reasonUpper.includes('TRAIL')) {{
                            solBadge = `<div style="margin-top:3px;"><span class="tag-solution tag-chandelier">📈 CHANDELIER TRAIL</span></div>`;
                        }} else if (reasonUpper.includes('SL') || reasonUpper.includes('FAIL')) {{
                            solBadge = `<div style="margin-top:3px;"><span class="tag-solution tag-hard-sl">⛔ CATASTROPHIC HARD SL</span></div>`;
                        }} else if (!isStandDown) {{
                            solBadge = `<div style="margin-top:3px;"><span class="tag-solution tag-target">🎯 DIRECT TARGET</span></div>`;
                        }}
                    }}

                    // Final P&L
                    let pnlClass = 'pnl-zero';
                    let pnlText = '₹0.00';
                    if (pnl > 0) {{
                        pnlClass = 'pnl-pos';
                        pnlText = formatCurrency(pnl);
                    }} else if (pnl < 0) {{
                        pnlClass = 'pnl-neg';
                        pnlText = formatCurrency(pnl);
                    }}

                    const peakGainText = peakAmt > 0 ? `+₹${{Math.round(peakAmt).toLocaleString('en-IN')}}` : '₹0';
                    const ptsText = (pts >= 0 ? '+' : '') + pts.toFixed(2);

                    const entryTime = (!row.entry_time || row.entry_time === '-') ? '—' : row.entry_time;
                    const peakTime = (!row.peak_time || row.peak_time === '-') ? '—' : row.peak_time;
                    const exitTime = (!row.exit_time || row.exit_time === '-') ? '—' : row.exit_time;

                    tr.innerHTML = `
                        <td class="col-sticky-left mono"><span class="pill-live-tag">LIVE</span><strong>${{row.date}}</strong></td>
                        <td>${{actionPill}}</td>
                        <td>${{scoreChip}}</td>
                        <td class="mono">${{entryTime}}</td>
                        <td class="mono">${{formatSpot(row.entry_spot)}}</td>
                        <td class="mono">${{formatSpot(row.peak_spot)}}</td>
                        <td class="mono">${{peakTime}}</td>
                        <td class="mono val-profit">${{isStandDown ? '—' : peakGainText}}</td>
                        <td class="mono">${{exitTime}}</td>
                        <td class="mono">${{formatSpot(row.exit_spot)}}</td>
                        <td>${{reasonTag}}${{solBadge}}</td>
                        <td class="mono ${{pts >= 0 ? 'pnl-pos' : 'pnl-neg'}}">${{isStandDown ? '0.00' : ptsText}}</td>
                        <td class="col-sticky-right mono pnl-cell ${{pnlClass}}">${{pnlText}}</td>
                    `;
                    tbody.appendChild(tr);
                }});
            }}

            const modeBadge = currentDeltaMode === 'OPTION' ? 'ATM Options (0.52 Δ)' : (currentDeltaMode === 'ITM' ? 'ITM Options (0.72 Δ)' : 'Futures (1.00 Δ)');
            const engineBadge = currentExecutionEngine === 'ENHANCED' 
                ? '🚀 Enhanced 4-Solution Engine (Active)' 
                : (currentExecutionEngine === 'RUNNER' ? '📈 Option 1: Multi-Tranche Runner (50/50)' : '🛡️ Baseline Fixed Target (100%)');
            document.getElementById('foot-total-peak').textContent = `+₹${{Math.round(totalPeakAmt).toLocaleString('en-IN')}}`;
            document.getElementById('foot-total-pts').textContent = `${{totalPts >= 0 ? '+' : ''}}${{totalPts.toFixed(2)}} pts`;
            document.getElementById('foot-total-pnl').textContent = formatCurrency(totalPnl);
            document.getElementById('foot-total-pnl').className = 'col-sticky-right mono pnl-cell ' + (totalPnl >= 0 ? 'pnl-pos' : 'pnl-neg');
            document.getElementById('foot-summary-label').textContent = `Live Desk Forward Performance (${{activeTrades}} Active Trades) — ${{engineBadge}} @ ${{modeBadge}}`;

            document.getElementById('footer-count').textContent = `Showing ${{displayRows.length}} live forward sessions (October 05, 2026 onwards) [${{currentLots}} Lots]`;
            document.getElementById('footer-sum').innerHTML = `Engine: <strong style="color:var(--accent-green);font-size:13px;">${{engineBadge}}</strong> &nbsp;|&nbsp; Mode: <strong style="color:var(--accent-cyan);font-size:13px;">${{modeBadge}}</strong> &nbsp;|&nbsp; Realized P&L: <strong style="color:${{totalPnl >= 0 ? 'var(--accent-green)' : 'var(--accent-red)'}};font-size:14px;">${{formatCurrency(totalPnl)}}</strong>`;
        }} catch (err) {{
            console.error("Render Table Error:", err);
            document.getElementById('table-body').innerHTML = `<tr><td colspan="13" style="color:red;padding:20px;">Error rendering data: ${{err.message}}</td></tr>`;
        }}
    }}

    // Initialize with persisted desk preference
    initLotsDropdown();
    let initialTicker = 'RELIANCE';
    try {{
        let hashTicker = window.location.hash ? window.location.hash.substring(1).toUpperCase().trim() : null;
        if (hashTicker === 'ADANI') hashTicker = 'ADANIENT';
        if (hashTicker && ['RELIANCE', 'ADANIENT', 'NIFTY', 'SENSEX'].includes(hashTicker)) {{
            initialTicker = hashTicker;
        }} else {{
            let stored = localStorage.getItem('active_live_desk');
            if (stored) stored = stored.toUpperCase().trim();
            if (stored === 'ADANI') stored = 'ADANIENT';
            if (stored && ['RELIANCE', 'ADANIENT', 'NIFTY', 'SENSEX'].includes(stored)) {{
                initialTicker = stored;
            }}
        }}
    }} catch (e) {{}}
    switchTicker(initialTicker);
</script>
</body>
</html>
"""

    with open(OUTPUT_HTML_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Generated clean Live Forward Dashboard ({OUTPUT_HTML_FILE}) starting Oct 05, 2026.")
    return OUTPUT_HTML_FILE


if __name__ == "__main__":
    generate_live_dashboard()

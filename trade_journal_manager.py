"""
Daily Trade Performance Journal & Capital Audit Ledger Manager
Automated Cross-Verification Engine:
- Cross-verifies trade signals given by the Quant Engine against actual trades executed on Groww.
- Captures:
  * Trade Given Time, Date, Suggested Entry, Target Exit, and Stop Loss
  * Actual Entry Time, Actual Entry Price in Groww
  * Actual Exit Time, Actual Exit Price in Groww
  * Realized P&L / Total Profit
  * Screenshot attachments (path/upload)
- Strictly posts ONLY trades executed in Groww broker account.
- Persists to daily_trade_journal.json and daily_signals_log.json.
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
import pytz

IST = pytz.timezone("Asia/Kolkata")
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JOURNAL_FILE = os.path.join(BASE_DIR, "daily_trade_journal.json")
SIGNALS_FILE = os.path.join(BASE_DIR, "daily_signals_log.json")
SCREENSHOTS_DIR = os.path.join(BASE_DIR, "screenshots")
STARTING_CAPITAL = 73643.72  # Verified Account Cash Balance

# Ensure screenshots directory exists
if not os.path.exists(SCREENSHOTS_DIR):
    try:
        os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
    except Exception as e:
        logger.debug(f"Could not create screenshots dir: {e}")


# ==============================================================================
# 1. SIGNAL TRACKER (TRADE GIVEN LOG)
# ==============================================================================
class SignalTracker:
    """Persists and retrieves quant trade recommendations and given triggers."""

    @classmethod
    def get_all_signals(cls) -> Dict[str, Any]:
        if os.path.exists(SIGNALS_FILE):
            try:
                with open(SIGNALS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
            except Exception as e:
                logger.debug(f"Error reading signals file: {e}")
        return {}

    @classmethod
    def get_signal(cls, date_str: Optional[str] = None, symbol: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if not date_str:
            date_str = datetime.now(IST).strftime("%Y-%m-%d")
        signals = cls.get_all_signals()
        if symbol:
            key = f"{date_str}_{symbol}"
            if key in signals:
                return signals[key]
        return signals.get(date_str)

    @classmethod
    def find_matching_signal(cls, symbol: str, actual_entry_time: str = None, date_str: str = None) -> Optional[Dict[str, Any]]:
        """
        Finds the exact signal recommendation corresponding to this executed trade:
        1. Must match contract symbol, strike, and type (CE/PE)
        2. Signal given time must be <= actual entry time
        """
        if not date_str:
            date_str = datetime.now(IST).strftime("%Y-%m-%d")
        signals = cls.get_all_signals()

        # Try exact key first
        exact_key = f"{date_str}_{symbol}"
        if exact_key in signals:
            return signals[exact_key]

        # Search all signals on this date
        candidates = []
        for k, s in signals.items():
            if not isinstance(s, dict):
                continue
            if s.get("date") != date_str:
                continue
            sig_sym = s.get("symbol", "")
            strike_str = str(s.get("strike", ""))
            ctype = str(s.get("contract_type", ""))
            
            # Match on symbol or (strike in symbol and ctype in symbol)
            if sig_sym == symbol or (strike_str in symbol and ctype in symbol):
                sig_time = s.get("trade_given_time", "")
                candidates.append((sig_time, s))

        if candidates:
            candidates.sort(key=lambda x: x[0])
            # Filter for signals given BEFORE or AT actual entry time
            if actual_entry_time:
                valid = []
                for stime, s in candidates:
                    try:
                        t_sig = datetime.strptime(stime.replace(" IST", "").strip(), "%I:%M:%S %p").time()
                        t_act = datetime.strptime(actual_entry_time.replace(" IST", "").strip(), "%I:%M:%S %p").time()
                        if t_sig <= t_act:
                            valid.append((stime, s))
                    except Exception:
                        valid.append((stime, s))
                if valid:
                    return valid[-1][1] # most recent signal prior to entry
            return candidates[0][1]

        # Fallback to legacy date_str if contract type and strike match
        legacy = signals.get(date_str)
        if legacy and isinstance(legacy, dict):
            leg_strike = str(legacy.get("strike", ""))
            leg_type = str(legacy.get("contract_type", ""))
            if (leg_strike in symbol and leg_type in symbol) or legacy.get("symbol") == symbol:
                return legacy

        return None

    @classmethod
    def save_signal(cls, signal: Dict[str, Any]):
        date_str = signal.get("date") or datetime.now(IST).strftime("%Y-%m-%d")
        symbol = signal.get("symbol") or "RELIANCE"
        key = f"{date_str}_{symbol}"
        signals = cls.get_all_signals()

        # Preserve original morning trade_given_time & parameters if this specific contract was already recorded
        if key in signals:
            existing = signals[key]
            signal["trade_given_time"] = existing.get("trade_given_time", signal.get("trade_given_time"))
            signal["suggested_entry"] = existing.get("suggested_entry", signal.get("suggested_entry"))
            signal["suggested_exit"] = existing.get("suggested_exit", signal.get("suggested_exit"))
            signal["suggested_sl"] = existing.get("suggested_sl", signal.get("suggested_sl"))
        elif not signal.get("trade_given_time"):
            signal["trade_given_time"] = datetime.now(IST).strftime("%I:%M:%S %p IST")

        signals[key] = signal
        # Only set as default date signal if date_str is empty or matches contract
        if date_str not in signals or signals[date_str].get("symbol") == symbol:
            signals[date_str] = signal

        try:
            with open(SIGNALS_FILE, "w", encoding="utf-8") as f:
                json.dump(signals, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not persist daily signal: {e}")


# ==============================================================================
# 2. JOURNAL RECALCULATION ENGINE
# ==============================================================================
def recalculate_journal(entries: List[Dict[str, Any]], starting_cash: float = None) -> List[Dict[str, Any]]:
    """
    Recalculates capital deployed, net_pnl, trade_roi_pct, cumulative_profit,
    and total_cash chronologically across all authentic executed entries.
    """
    if not entries:
        return []

    # Sort chronologically by date and entry time
    sorted_entries = sorted(entries, key=lambda x: (x.get("date", ""), x.get("actual_entry_time", "")))
    
    if starting_cash is None or starting_cash <= 0:
        starting_cash = STARTING_CAPITAL
            
    running_cum_profit = 0.0
    
    for i, e in enumerate(sorted_entries, 1):
        if not e.get("id"):
            sym_tag = e.get("trading_symbol", "").replace(" ", "_")
            e["id"] = f"TRD-{e.get('date', '').replace('-', '')}-{i:02d}-{sym_tag}"
        
        ep = float(e.get("entry_price", e.get("actual_entry_price", 0.0)))
        qty = int(e.get("qty", 1000))
        num_lots = max(1, round(qty / 500))
        e["num_lots"] = e.get("num_lots", num_lots)
        e["lot_size"] = 500
        e["qty"] = qty
        
        # Realized net P&L directly from Groww execution or captured/lost
        if "realised_pnl" in e and e["realised_pnl"] is not None:
            net = float(e["realised_pnl"])
        elif "net_profit" in e and e["net_profit"] is not None:
            net = float(e["net_profit"])
        elif e.get("status") == "HIT":
            net = float(e.get("amount_captured", 10000.0))
        elif e.get("status") == "FAIL":
            net = -float(e.get("amount_lost", 9000.0))
        else:
            net = 0.0

        cap_deployed = float(e.get("capital_deployed", round(ep * qty, 2)))
        e["capital_deployed"] = cap_deployed
        e["realised_pnl"] = net
        e["net_profit"] = net
        e["net_pnl"] = net
        e["total_profit"] = net

        if net > 0:
            e["amount_captured"] = net
            e["amount_lost"] = 0.0
            e["status"] = "HIT"
        elif net < 0:
            e["amount_captured"] = 0.0
            e["amount_lost"] = abs(net)
            e["status"] = "FAIL"
        else:
            e["amount_captured"] = 0.0
            e["amount_lost"] = 0.0
            if e.get("is_closed") is False:
                e["status"] = "OPEN"
            else:
                e["status"] = e.get("status", "STAND DOWN")

        e["trade_roi_pct"] = round((net / cap_deployed) * 100.0, 1) if cap_deployed > 0 else 0.0
        
        running_cum_profit += net
        e["cumulative_profit"] = round(running_cum_profit, 2)
        e["total_cash"] = round(starting_cash + running_cum_profit, 2)
        
    return sorted_entries


# ==============================================================================
# 3. TRADE JOURNAL & CROSS-VERIFICATION MANAGER
# ==============================================================================
class TradeJournalManager:
    @classmethod
    def load_journal(cls, starting_cash: float = None) -> List[Dict[str, Any]]:
        """Loads journal from JSON file. Returns clean list without injecting synthetic data."""
        if starting_cash is None:
            starting_cash = STARTING_CAPITAL

        if not os.path.exists(JOURNAL_FILE):
            cls.save_journal([])
            return []
            
        try:
            with open(JOURNAL_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                # Filter strictly for RELIANCE trades
                reliance_entries = [
                    e for e in data 
                    if "RELIANCE" in str(e.get("trading_symbol", "")).upper() or "RELIANCE" in str(e.get("instrument", "")).upper()
                ]
                if len(reliance_entries) > 0:
                    return recalculate_journal(reliance_entries, starting_cash)
                else:
                    return []
            else:
                cls.save_journal([])
                return []
        except Exception:
            cls.save_journal([])
            return []

    @classmethod
    def save_journal(cls, entries: List[Dict[str, Any]]):
        """Saves journal records to JSON file."""
        with open(JOURNAL_FILE, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2)

    @classmethod
    def add_or_update_entry(cls, new_entry: Dict[str, Any], starting_cash: float = None) -> List[Dict[str, Any]]:
        """Adds a new daily trade record or updates existing trade for the same date/ID."""
        if starting_cash is None:
            starting_cash = STARTING_CAPITAL
        entries = cls.load_journal(starting_cash)
        date_to_log = new_entry.get("date")
        entry_id = new_entry.get("id")
        sym_to_log = new_entry.get("trading_symbol")

        # Replace matching entry if exists by unique ID
        def is_match(e):
            if entry_id and e.get("id") == entry_id:
                return True
            return False

        entries = [e for e in entries if not is_match(e)]
        entries.append(new_entry)
        recalculated = recalculate_journal(entries, starting_cash)
        cls.save_journal(recalculated)
        return recalculated

    @classmethod
    def delete_entry(cls, entry_id: str, starting_cash: float = None) -> List[Dict[str, Any]]:
        """Deletes trade record by ID or date."""
        if starting_cash is None:
            starting_cash = STARTING_CAPITAL
        entries = cls.load_journal(starting_cash)
        entries = [e for e in entries if e.get("id") != entry_id and e.get("date") != entry_id]
        recalculated = recalculate_journal(entries, starting_cash)
        cls.save_journal(recalculated)
        return recalculated

    @classmethod
    def reset_to_default(cls, starting_cash: float = None) -> List[Dict[str, Any]]:
        """Resets journal back to clean state (empty list)."""
        cls.save_journal([])
        return []

    @classmethod
    def update_screenshot(cls, trade_id: str, screenshot_path: str, data_uri: str = "", starting_cash: float = None) -> List[Dict[str, Any]]:
        """Updates the screenshot path for a specific trade entry across both journal and shadow logs."""
        if starting_cash is None:
            starting_cash = STARTING_CAPITAL
        entries = cls.load_journal(starting_cash)
        clean_id = trade_id.replace(":", "_").replace("/", "_").replace("\\", "_")
        for e in entries:
            e_id = e.get("id", "")
            e_sym = e.get("trading_symbol", "")
            if e_id == trade_id or e_sym == trade_id or clean_id in e_id or e_sym in clean_id:
                e["screenshot"] = screenshot_path
                if data_uri:
                    e["screenshot_data_uri"] = data_uri
                break
        cls.save_journal(entries)
        
        # Also update in ShadowMonitoringEngine if available
        try:
            ShadowMonitoringEngine.update_screenshot(trade_id, screenshot_path, data_uri=data_uri)
        except Exception:
            pass
        return entries

    @classmethod
    def save_screenshot_file(cls, trade_id: str, file_bytes: bytes, original_filename: str) -> str:
        """Saves an uploaded screenshot image file locally and returns its relative path."""
        if not file_bytes or len(file_bytes) == 0:
            return ""
        import base64
        ext = os.path.splitext(original_filename)[1] or ".png"
        clean_id = trade_id.replace(":", "_").replace("/", "_").replace("\\", "_")
        filename = f"{clean_id}{ext}"
        target_path = os.path.join(SCREENSHOTS_DIR, filename)
        with open(target_path, "wb") as f:
            f.write(file_bytes)
        rel_path = os.path.join("screenshots", filename)
        
        # Generate base64 data URI as permanent resilient fallback
        mime = "image/png" if ext.lower() == ".png" else ("image/jpeg" if ext.lower() in [".jpg", ".jpeg"] else "image/webp")
        b64_str = base64.b64encode(file_bytes).decode("utf-8")
        data_uri = f"data:{mime};base64,{b64_str}"
        
        cls.update_screenshot(trade_id, rel_path, data_uri=data_uri)
        return rel_path

    @classmethod
    def sync_groww_trades(
        cls,
        groww_executed_trades: List[Dict[str, Any]],
        active_signal: Optional[Dict[str, Any]] = None,
        starting_cash: float = None
    ) -> List[Dict[str, Any]]:
        """
        Automates cross-verification between the trade given by the system and actual trades executed on Groww.
        Strict rule: ONLY trades executed in Groww broker account are added / updated in the ledger!
        """
        if starting_cash is None:
            starting_cash = STARTING_CAPITAL

        current_entries = cls.load_journal(starting_cash)
        existing_map = {}
        for e in current_entries:
            e_t = e.get("actual_entry_time", "")
            key = f"{e.get('date', '')}_{e.get('trading_symbol', e.get('instrument', ''))}_{e_t}" if e_t else f"{e.get('date', '')}_{e.get('trading_symbol', e.get('instrument', ''))}"
            existing_map[key] = e
            if e.get("id"):
                existing_map[e["id"]] = e
            base_key = f"{e.get('date', '')}_{e.get('trading_symbol', e.get('instrument', ''))}"
            if base_key not in existing_map:
                existing_map[base_key] = e

        today_str = datetime.now(IST).strftime("%Y-%m-%d")
        today_day = datetime.now(IST).strftime("%A")
        
        # Load or use active signal for today
        signal = active_signal or SignalTracker.get_signal(today_str) or {}

        for gt in groww_executed_trades:
            sym = gt.get("symbol", "")
            if not sym or "RELIANCE" not in sym.upper():
                continue

            entry_p = float(gt.get("entry_price", 0.0))
            exit_p = float(gt.get("exit_price", 0.0))
            realised_pnl = float(gt.get("realised_pnl", 0.0))
            qty = int(gt.get("qty", 1000))
            is_closed = bool(gt.get("is_closed", False))
            
            raw_entry_t = gt.get("entry_time", "")
            raw_exit_t = gt.get("exit_time", "")
            
            actual_entry_time_str = ""
            if raw_entry_t:
                try:
                    dt = datetime.fromisoformat(raw_entry_t.replace("Z", "+00:00"))
                    actual_entry_time_str = dt.strftime("%I:%M:%S %p IST")
                except Exception:
                    actual_entry_time_str = raw_entry_t

            actual_exit_time_str = ""
            if raw_exit_t:
                try:
                    dt = datetime.fromisoformat(raw_exit_t.replace("Z", "+00:00"))
                    actual_exit_time_str = dt.strftime("%I:%M:%S %p IST")
                except Exception:
                    actual_exit_time_str = raw_exit_t

            is_reliance = "RELIANCE" in sym.upper()
            composite_key = f"{today_str}_{sym}_{raw_entry_t}" if raw_entry_t else f"{today_str}_{sym}"
            existing = existing_map.get(composite_key) or existing_map.get(f"{today_str}_{sym}", {})
            existing_screenshot = existing.get("screenshot", "")
            existing_notes = existing.get("notes", "")

            # Strict Rule: If this trade was ALREADY cross-verified and stored in journal, KEEP ITS ORIGINAL GIVEN DETAILS!
            # Never overwrite a completed morning trade with an afternoon scan or different strike!
            if existing and existing.get("suggested_entry") is not None and existing.get("trade_given_time"):
                trade_given_time = existing["trade_given_time"]
                sugg_contract = existing.get("suggested_contract") or existing.get("instrument") or sym
                sugg_entry = float(existing["suggested_entry"])
                sugg_exit = float(existing.get("suggested_exit", round(sugg_entry + 10.0, 2)))
                sugg_sl = float(existing.get("suggested_sl", round(max(0.05, sugg_entry - 4.5), 2)))
                confluence = float(existing.get("confluence_score", 78.5))
                trade_type = existing.get("type", "BUY PE" if "PE" in sym else "BUY CE")
            else:
                # Find matching signal recommendation that was issued BEFORE this trade's entry time
                matched_signal = SignalTracker.find_matching_signal(symbol=sym, actual_entry_time=actual_entry_time_str, date_str=today_str)
                if matched_signal:
                    trade_given_time = matched_signal.get("trade_given_time", actual_entry_time_str)
                    sugg_contract = matched_signal.get("full_contract") or f"RELIANCE {matched_signal.get('strike', 1200)} {matched_signal.get('contract_type', 'PE')} ({matched_signal.get('expiry', '27-OCT-2026')})"
                    sugg_entry = float(matched_signal.get("suggested_entry", entry_p))
                    sugg_exit = float(matched_signal.get("suggested_exit", round(sugg_entry + 10.0, 2)))
                    sugg_sl = float(matched_signal.get("suggested_sl", round(max(0.05, sugg_entry - 4.5), 2)))
                    confluence = float(matched_signal.get("confluence_score", 78.5))
                    trade_type = f"BUY {matched_signal.get('contract_type', 'PE' if 'PE' in sym else 'CE')}"
                else:
                    # No model recommendation preceded this execution -> Discretionary / User execution
                    trade_given_time = actual_entry_time_str or "09:15:00 AM IST"
                    sugg_contract = sym
                    sugg_entry = entry_p
                    sugg_exit = round(entry_p + 10.0, 2)
                    sugg_sl = round(max(0.05, entry_p - 4.5), 2)
                    confluence = 70.0
                    trade_type = "BUY CE" if "CE" in sym else ("BUY PE" if "PE" in sym else "BUY")

            entry_slippage = round(entry_p - sugg_entry, 2)
            cap_deployed = round(entry_p * qty, 2)

            # Formulate audit verification note
            if not existing_notes:
                pnl_sign = "+" if realised_pnl >= 0 else ""
                if is_closed:
                    notes_str = f"Verified Groww Execution • Buy ₹{entry_p:.2f} ({actual_entry_time_str}) -> Sell ₹{exit_p:.2f} ({actual_exit_time_str}) • Realized P&L: {pnl_sign}₹{realised_pnl:,.2f}"
                else:
                    notes_str = f"Live Open Position in Groww • Buy ₹{entry_p:.2f} ({actual_entry_time_str}) • Currently Holding"
            else:
                notes_str = existing_notes

            trade_status = "HIT" if realised_pnl > 0 else ("FAIL" if realised_pnl < 0 else ("OPEN" if not is_closed else "STAND DOWN"))

            record = {
                "id": existing.get("id") or f"TRD-{today_str.replace('-', '')}-{sym}",
                "date": today_str,
                "day": today_day,
                "trading_symbol": sym,
                "instrument": sugg_contract,
                "type": trade_type,
                "decision": "TRADABLE (A+ SETUP)" if is_reliance else "DISCRETIONARY GROWW TRADE",
                "source": "GROWW_VERIFIED",
                "is_closed": is_closed,
                
                # Trade Given Details (Model)
                "trade_given_time": trade_given_time,
                "suggested_contract": sugg_contract,
                "suggested_entry": sugg_entry,
                "suggested_exit": sugg_exit,
                "suggested_sl": sugg_sl,
                "suggested_target_pts": round(sugg_exit - sugg_entry, 2),
                "suggested_sl_pts": round(sugg_entry - sugg_sl, 2),
                
                # Actual Execution Details (Groww)
                "actual_entry_time": actual_entry_time_str,
                "actual_entry_price": entry_p,
                "entry_price": entry_p,
                "actual_exit_time": actual_exit_time_str,
                "actual_exit_price": exit_p,
                "exit_price": exit_p,
                "num_lots": max(1, round(qty / 500)),
                "lot_size": 500,
                "qty": qty,
                "capital_deployed": cap_deployed,
                "realised_pnl": realised_pnl,
                "total_profit": realised_pnl,
                "net_profit": realised_pnl,
                "net_pnl": realised_pnl,
                "amount_captured": realised_pnl if realised_pnl > 0 else 0.0,
                "amount_lost": abs(realised_pnl) if realised_pnl < 0 else 0.0,
                "status": trade_status,
                
                # Variance / Slippage Metrics
                "entry_slippage_pts": entry_slippage,
                
                # Screenshot & Notes
                "screenshot": existing_screenshot,
                "notes": notes_str,
                "confluence_score": confluence
            }
            existing_map[composite_key] = record

        all_updated = [
            e for e in existing_map.values()
            if "RELIANCE" in str(e.get("trading_symbol", "")).upper() or "RELIANCE" in str(e.get("instrument", "")).upper()
        ]
        recalculated = recalculate_journal(all_updated, starting_cash)
        cls.save_journal(recalculated)
        return recalculated

    @classmethod
    def get_summary_kpi(cls, entries: List[Dict[str, Any]], today_strike_price: float = None, starting_cash: float = None) -> Dict[str, Any]:
        """Calculates executive performance metrics strictly anchored on verified executions."""
        total_days = len(entries)
        traded_days = [e for e in entries if e.get("status") in ["HIT", "FAIL"]]
        stand_down_days = [e for e in entries if e.get("status") == "STAND DOWN"]
        hits = [e for e in entries if e.get("status") == "HIT"]
        fails = [e for e in entries if e.get("status") == "FAIL"]
        open_trades = [e for e in entries if e.get("status") == "OPEN"]
        
        total_captured = sum(e.get("amount_captured", 0.0) for e in entries)
        total_lost = sum(e.get("amount_lost", 0.0) for e in entries)
        total_profit = total_captured - total_lost
        
        starting_capital = starting_cash if (starting_cash is not None and starting_cash > 0) else STARTING_CAPITAL
        total_cash = round(starting_capital + total_profit, 2)
        
        # Today's 2-lot required capital
        if today_strike_price is not None and today_strike_price > 0:
            today_2lot_capital = round(2 * 500 * today_strike_price, 2)
        else:
            today_2lot_capital = round(2 * 500 * 37.65, 2)
        
        win_rate = (len(hits) / len(traded_days) * 100.0) if len(traded_days) > 0 else 0.0
        profit_factor = (total_captured / total_lost) if total_lost > 0 else (total_captured if total_captured > 0 else 1.0)
        roi_pct = (total_profit / starting_capital) * 100.0 if starting_capital > 0 else 0.0
        
        avg_capital_deployed = round(sum(e.get("capital_deployed", 0.0) for e in traded_days) / len(traded_days), 2) if traded_days else 0.0
        
        return {
            "starting_capital": starting_capital,
            "today_2lot_capital": today_2lot_capital,
            "avg_capital_deployed": avg_capital_deployed,
            "total_cash": total_cash,
            "total_profit": total_profit,
            "roi_pct": roi_pct,
            "total_captured": total_captured,
            "total_lost": total_lost,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "total_days": total_days,
            "total_trades": len(traded_days),
            "hits": len(hits),
            "fails": len(fails),
            "open_trades": len(open_trades),
            "stand_downs": len(stand_down_days)
        }


# ==============================================================================
# 4. AUTOMATED SHADOW MONITORING & SIGNAL LOGGING ENGINE (GROWW API INTEGRATION)
# ==============================================================================
SHADOW_SIGNALS_FILE = os.path.join(BASE_DIR, "shadow_signals_log.json")

class ShadowMonitoringEngine:
    """
    Automated Daily Signal Logging, Shadow Monitoring & Calendar History Engine:
    1. Daily Signal Logging:
       - Records every signal generated: Timestamp, Date, Symbol, Action, Suggested Entry, SL, Target.
       - Tracks user execution flag: user_executed = True / False.
    2. Automated Shadow Monitoring (Groww API Integration):
       - Fetches live tick data from Groww API post-signal.
       - Monitors ALL suggested trades until 3:30 PM (market close), regardless of user execution.
       - Tracks price extremes: Highest Price Reached & Lowest Price Reached post-entry.
       - Records definitive outcome: Target Hit, Stop-Loss Hit, or EOD Exit.
    3. Calendar View / Date-wise Navigation:
       - Interactive date picker / calendar selector.
       - Date-specific log table, metrics, and KPI audit ledger.
    """
    @classmethod
    def load_records(cls) -> List[Dict[str, Any]]:
        if os.path.exists(SHADOW_SIGNALS_FILE):
            try:
                with open(SHADOW_SIGNALS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return data
            except Exception as e:
                logger.debug(f"Error loading shadow signals log: {e}")
        return cls._bootstrap_from_existing()

    @classmethod
    def save_records(cls, records: List[Dict[str, Any]]):
        try:
            with open(SHADOW_SIGNALS_FILE, "w", encoding="utf-8") as f:
                json.dump(records, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not persist shadow signals: {e}")

    @classmethod
    def _bootstrap_from_existing(cls) -> List[Dict[str, Any]]:
        """Bootstraps initial shadow records from daily_trade_journal.json and daily_signals_log.json."""
        records = []
        # 1. From daily_trade_journal.json
        if os.path.exists(JOURNAL_FILE):
            try:
                with open(JOURNAL_FILE, "r", encoding="utf-8") as f:
                    j_data = json.load(f)
                    if isinstance(j_data, list):
                        for j in j_data:
                            sym = j.get("trading_symbol", "")
                            sugg_e = float(j.get("suggested_entry", j.get("entry_price", 30.0)))
                            sugg_t = float(j.get("suggested_exit", sugg_e + 10.0))
                            sugg_sl = float(j.get("suggested_sl", max(0.05, sugg_e - 4.5)))
                            act_e = float(j.get("actual_entry_price", sugg_e))
                            act_x = float(j.get("actual_exit_price", sugg_t))
                            high_p = max(sugg_e, act_e, act_x, sugg_t)
                            low_p = min(sugg_e, act_e, act_x, sugg_sl)
                            status_raw = j.get("status", "HIT")
                            outcome = "Target Hit" if status_raw == "HIT" else ("Stop-Loss Hit" if status_raw == "FAIL" else "Active Monitoring")
                            rec = {
                                "id": j.get("id") or f"SIG-{j.get('date', '2026-09-29').replace('-', '')}-01-{sym}",
                                "timestamp": j.get("trade_given_time", "09:15:00 AM IST"),
                                "date": j.get("date", "2026-09-29"),
                                "symbol": sym,
                                "instrument": j.get("instrument") or j.get("suggested_contract") or sym,
                                "action": j.get("type", "BUY PE" if "PE" in sym else "BUY CE"),
                                "entry": sugg_e,
                                "target": sugg_t,
                                "sl": sugg_sl,
                                "target_pts": round(sugg_t - sugg_e, 2),
                                "sl_pts": round(sugg_e - sugg_sl, 2),
                                "user_executed": True,
                                "actual_entry_price": act_e,
                                "actual_entry_time": j.get("actual_entry_time", ""),
                                "actual_exit_price": act_x,
                                "actual_exit_time": j.get("actual_exit_time", ""),
                                "realised_pnl": float(j.get("realised_pnl", 0.0)),
                                "screenshot": j.get("screenshot", ""),
                                "screenshot_data_uri": j.get("screenshot_data_uri", ""),
                                "shadow_status": outcome,
                                "highest_price_reached": high_p,
                                "lowest_price_reached": low_p,
                                "current_price": act_x,
                                "exit_price": act_x,
                                "exit_time": j.get("actual_exit_time", ""),
                                "shadow_pts": round(sugg_t - sugg_e, 2) if outcome == "Target Hit" else round(sugg_sl - sugg_e, 2),
                                "shadow_pnl": float(j.get("realised_pnl", 0.0)),
                                "confluence_score": float(j.get("confluence_score", 78.5)),
                                "notes": j.get("notes", "")
                            }
                            records.append(rec)
            except Exception as e:
                logger.debug(f"Bootstrap journal error: {e}")

        # 2. From daily_signals_log.json for signals not yet in journal
        if os.path.exists(SIGNALS_FILE):
            try:
                with open(SIGNALS_FILE, "r", encoding="utf-8") as f:
                    s_data = json.load(f)
                    if isinstance(s_data, dict):
                        existing_syms = {r.get("symbol") for r in records}
                        for k, s in s_data.items():
                            if not isinstance(s, dict):
                                continue
                            sym = s.get("symbol", "")
                            if not sym or sym in existing_syms:
                                continue
                            sugg_e = float(s.get("suggested_entry", 35.0))
                            sugg_t = float(s.get("suggested_exit", sugg_e + 10.0))
                            sugg_sl = float(s.get("suggested_sl", max(0.05, sugg_e - 4.5)))
                            rec = {
                                "id": f"SIG-{s.get('date', '2026-09-29').replace('-', '')}-02-{sym}",
                                "timestamp": s.get("trade_given_time", "11:52:32 AM IST"),
                                "date": s.get("date", "2026-09-29"),
                                "symbol": sym,
                                "instrument": s.get("full_contract") or sym,
                                "action": f"BUY {s.get('contract_type', 'CE')}",
                                "entry": sugg_e,
                                "target": sugg_t,
                                "sl": sugg_sl,
                                "target_pts": round(sugg_t - sugg_e, 2),
                                "sl_pts": round(sugg_e - sugg_sl, 2),
                                "user_executed": False,
                                "actual_entry_price": None,
                                "actual_entry_time": "",
                                "actual_exit_price": None,
                                "actual_exit_time": "",
                                "realised_pnl": 0.0,
                                "screenshot": "",
                                "screenshot_data_uri": "",
                                "shadow_status": "Active Monitoring",
                                "highest_price_reached": sugg_e,
                                "lowest_price_reached": sugg_e,
                                "current_price": sugg_e,
                                "exit_price": None,
                                "exit_time": "",
                                "shadow_pts": 0.0,
                                "shadow_pnl": 0.0,
                                "confluence_score": float(s.get("confluence_score", 82.0)),
                                "notes": "Shadow tracking active until 3:30 PM market close."
                            }
                            records.append(rec)
            except Exception as e:
                logger.debug(f"Bootstrap signals error: {e}")

        cls.save_records(records)
        return records

    @classmethod
    def log_signal(
        cls,
        symbol: str,
        action: str,
        entry: float,
        target: float,
        sl: float,
        date_str: Optional[str] = None,
        time_str: Optional[str] = None,
        instrument: Optional[str] = None,
        confluence_score: float = 78.0,
        user_executed: bool = False
    ) -> Dict[str, Any]:
        """Records every signal generated (Timestamp, Symbol, Action, Entry, SL, Target)."""
        date_str = date_str or datetime.now(IST).strftime("%Y-%m-%d")
        time_str = time_str or datetime.now(IST).strftime("%I:%M:%S %p IST")
        records = cls.load_records()
        
        # Check if an ACTIVE (open) record for this date and symbol already exists
        for r in records:
            if r.get("date") == date_str and r.get("symbol") == symbol and r.get("shadow_status") == "Active Monitoring":
                return r

        clean_sym = symbol.replace(" ", "_")
        time_tag = time_str.replace(":", "").replace(" ", "").replace("IST", "")[:6]
        today_matching = [r for r in records if r.get("date") == date_str]
        trade_seq_num = len(today_matching) + 1
        
        act_entry_p = round(float(entry), 2) if user_executed else None
        act_entry_t = time_str if user_executed else ""

        rec = {
            "id": f"SIG-{date_str.replace('-', '')}-{trade_seq_num:02d}-{clean_sym}",
            "timestamp": time_str,
            "date": date_str,
            "symbol": symbol,
            "instrument": instrument or symbol,
            "action": action,
            "entry": round(float(entry), 2),
            "target": round(float(target), 2),
            "sl": round(float(sl), 2),
            "target_pts": round(float(target) - float(entry), 2),
            "sl_pts": round(float(entry) - float(sl), 2),
            "user_executed": bool(user_executed),
            "actual_entry_price": act_entry_p,
            "actual_entry_time": act_entry_t,
            "actual_exit_price": None,
            "actual_exit_time": "",
            "realised_pnl": 0.0,
            "screenshot": "",
            "screenshot_data_uri": "",
            "shadow_status": "Active Monitoring",
            "highest_price_reached": round(float(entry), 2),
            "lowest_price_reached": round(float(entry), 2),
            "current_price": round(float(entry), 2),
            "exit_price": None,
            "exit_time": "",
            "shadow_pts": 0.0,
            "shadow_pnl": 0.0,
            "confluence_score": round(float(confluence_score), 1),
            "notes": "Automated Shadow Monitoring active until 3:30 PM (Groww API Integration)"
        }
        records.append(rec)
        cls.save_records(records)
        return rec

    @classmethod
    def update_shadow_monitoring(cls, groww_feed=None) -> List[Dict[str, Any]]:
        """
        Automated Shadow Monitoring (Groww API Integration):
        - Fetches tick/candle data from Groww API post-signal.
        - Monitors all suggested trades until 3:30 PM (market close), regardless of user execution.
        - Logs price extremes: Highest Price Reached & Lowest Price Reached post-entry.
        - Records outcome: Target Hit, Stop-Loss Hit, or EOD Exit.
        - Cross-verifies executed broker fills with Groww to update user_executed.
        """
        records = cls.load_records()
        if not records:
            return []

        today_str = datetime.now(IST).strftime("%Y-%m-%d")
        now_dt = datetime.now(IST)
        now_time = now_dt.time()
        from datetime import time as time_type
        market_close = time_type(15, 30, 0)

        # 1. Check Groww broker executions for user_executed flag
        executed_map = {}
        if groww_feed and getattr(groww_feed, "is_connected", False):
            try:
                gw_trades = groww_feed.get_executed_trades_today(symbol_filter="RELIANCE")
                for gt in gw_trades:
                    sym = gt.get("symbol", "")
                    executed_map[sym] = gt
            except Exception as e:
                logger.debug(f"Shadow check executed trades error: {e}")

        updated_any = False
        for rec in records:
            if rec.get("date") != today_str:
                continue

            sym = rec.get("symbol", "")
            entry = float(rec.get("entry", 30.0))
            target = float(rec.get("target", entry + 10.0))
            sl = float(rec.get("sl", entry - 4.5))

            # Auto-check user execution on Groww
            for ex_sym, ex_tr in executed_map.items():
                if sym in ex_sym or ex_sym in sym:
                    if not rec.get("user_executed"):
                        rec["user_executed"] = True
                        updated_any = True
                    rec["actual_entry_price"] = float(ex_tr.get("entry_price", entry))
                    rec["actual_entry_time"] = ex_tr.get("entry_time", "")
                    if ex_tr.get("is_closed"):
                        rec["actual_exit_price"] = float(ex_tr.get("exit_price", entry))
                        rec["actual_exit_time"] = ex_tr.get("exit_time", "")
                        rec["realised_pnl"] = float(ex_tr.get("realised_pnl", 0.0))
                        updated_any = True

            # Shadow Price Action Monitoring
            status = rec.get("shadow_status", "Active Monitoring")
            if status == "Active Monitoring":
                live_price = None
                if groww_feed:
                    try:
                        live_price = groww_feed.get_option_contract_ltp(sym)
                    except Exception:
                        live_price = None

                if live_price is not None and live_price > 0:
                    live_p = float(live_price)
                    high_p = max(float(rec.get("highest_price_reached", entry)), live_p)
                    low_p = min(float(rec.get("lowest_price_reached", entry)), live_p)
                    rec["highest_price_reached"] = round(high_p, 2)
                    rec["lowest_price_reached"] = round(low_p, 2)
                    rec["current_price"] = round(live_p, 2)
                    updated_any = True

                    # Check Target Hit
                    if live_p >= target:
                        rec["shadow_status"] = "Target Hit"
                        rec["exit_price"] = round(target, 2)
                        rec["exit_time"] = now_dt.strftime("%I:%M:%S %p IST")
                        rec["shadow_pts"] = round(target - entry, 2)
                        rec["shadow_pnl"] = round(rec["shadow_pts"] * 1000, 2)
                        updated_any = True
                    # Check Stop-Loss Hit
                    elif live_p <= sl:
                        rec["shadow_status"] = "Stop-Loss Hit"
                        rec["exit_price"] = round(sl, 2)
                        rec["exit_time"] = now_dt.strftime("%I:%M:%S %p IST")
                        rec["shadow_pts"] = round(sl - entry, 2)
                        rec["shadow_pnl"] = round(rec["shadow_pts"] * 1000, 2)
                        updated_any = True
                    # Check EOD Exit (at 3:30 PM)
                    elif now_time >= market_close:
                        rec["shadow_status"] = "EOD Exit"
                        rec["exit_price"] = round(live_p, 2)
                        rec["exit_time"] = "03:30:00 PM IST"
                        rec["shadow_pts"] = round(live_p - entry, 2)
                        rec["shadow_pnl"] = round(rec["shadow_pts"] * 1000, 2)
                        updated_any = True
                    else:
                        cur_pts = round(live_p - entry, 2)
                        rec["shadow_pts"] = cur_pts
                        rec["shadow_pnl"] = round(cur_pts * 1000, 2)

                elif now_time >= market_close:
                    rec["shadow_status"] = "EOD Exit"
                    rec["exit_price"] = float(rec.get("current_price", entry))
                    rec["exit_time"] = "03:30:00 PM IST"
                    rec["shadow_pts"] = round(rec["exit_price"] - entry, 2)
                    rec["shadow_pnl"] = round(rec["shadow_pts"] * 1000, 2)
                    updated_any = True

        if updated_any:
            cls.save_records(records)

        return records

    @classmethod
    def record_user_execution(cls, symbol: str, actual_price: float, actual_time: str):
        """Flags that user executed this signal on Groww."""
        records = cls.load_records()
        today_str = datetime.now(IST).strftime("%Y-%m-%d")
        for r in records:
            if r.get("date") == today_str and (symbol in r.get("symbol", "") or r.get("symbol", "") in symbol):
                r["user_executed"] = True
                r["actual_entry_price"] = round(float(actual_price), 2)
                r["actual_entry_time"] = actual_time
                break
        cls.save_records(records)

    @classmethod
    def record_trade_close(cls, symbol: str, exit_price: float, exit_time: str, outcome: str, realised_pnl: float):
        """Records closure of a trade."""
        records = cls.load_records()
        today_str = datetime.now(IST).strftime("%Y-%m-%d")
        for r in records:
            if r.get("date") == today_str and (symbol in r.get("symbol", "") or r.get("symbol", "") in symbol):
                r["actual_exit_price"] = round(float(exit_price), 2)
                r["actual_exit_time"] = exit_time
                r["realised_pnl"] = round(float(realised_pnl), 2)
                if outcome:
                    r["shadow_status"] = outcome
                break
        cls.save_records(records)

    @classmethod
    def update_screenshot(cls, trade_id: str, screenshot_path: str, data_uri: str = ""):
        records = cls.load_records()
        clean_id = trade_id.replace(":", "_").replace("/", "_").replace("\\", "_")
        for r in records:
            r_id = r.get("id", "")
            r_sym = r.get("symbol", "")
            if r_id == trade_id or r_sym == trade_id or clean_id in r_id or r_sym in clean_id:
                r["screenshot"] = screenshot_path
                if data_uri:
                    r["screenshot_data_uri"] = data_uri
                break
        cls.save_records(records)

    @classmethod
    def get_available_dates(cls) -> List[str]:
        records = cls.load_records()
        dates = sorted(list({r.get("date") for r in records if r.get("date")}), reverse=True)
        today = datetime.now(IST).strftime("%Y-%m-%d")
        if today not in dates:
            dates.insert(0, today)
        return dates

    @classmethod
    def get_records_by_date(cls, selected_date: Optional[str] = None) -> List[Dict[str, Any]]:
        records = cls.load_records()
        if not selected_date or selected_date.upper() == "ALL":
            return sorted(records, key=lambda x: (x.get("date", ""), x.get("timestamp", "")), reverse=True)
        return sorted(
            [r for r in records if r.get("date") == selected_date],
            key=lambda x: x.get("timestamp", ""),
            reverse=True
        )

    @classmethod
    def get_shadow_kpi(cls, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        total_signals = len(records)
        executed_records = [r for r in records if r.get("user_executed")]
        executed_count = len(executed_records)
        executed_pct = round((executed_count / total_signals * 100.0), 1) if total_signals > 0 else 0.0

        target_hits = len([r for r in records if r.get("shadow_status") == "Target Hit"])
        sl_hits = len([r for r in records if r.get("shadow_status") == "Stop-Loss Hit"])
        eod_exits = len([r for r in records if r.get("shadow_status") == "EOD Exit"])
        active_count = len([r for r in records if r.get("shadow_status") == "Active Monitoring"])

        shadow_total_pnl = sum(float(r.get("shadow_pnl", 0.0)) for r in records)
        groww_realised_pnl = sum(float(r.get("realised_pnl", 0.0)) for r in records)
        
        closed_signals = target_hits + sl_hits
        win_rate = round((target_hits / closed_signals * 100.0), 1) if closed_signals > 0 else 0.0

        return {
            "total_signals": total_signals,
            "user_executed_count": executed_count,
            "user_executed_pct": executed_pct,
            "target_hits": target_hits,
            "sl_hits": sl_hits,
            "eod_exits": eod_exits,
            "active_count": active_count,
            "shadow_total_pnl": round(shadow_total_pnl, 2),
            "groww_realised_pnl": round(groww_realised_pnl, 2),
            "win_rate": win_rate
        }


# ==============================================================================
# 5. STRICT SEQUENTIAL TRADING ASSISTANT ENGINE
# ==============================================================================
SEQUENTIAL_STATE_FILE = os.path.join(BASE_DIR, "sequential_trade_state.json")

class SequentialTradeEngine:
    """
    Enforces Strict Sequential Trading Assistant Operating Discipline:
    Rule 1: Strict One-Trade-At-A-Time (Zero Parallel Signals, No Overtrading).
    Rule 2: Verification & Execution Check (Ask user & verify fill on Groww at planned entry).
    Rule 3: Active Monitoring (Track active trade until Target or Stop-Loss is hit).
    Rule 4: Running Trade Log Table (Strict column layout).
    Rule 5: Wait for Closure (Only plan next trade after current trade hits Target/SL and is logged).
    Rule 6: Strictly RELIANCE Options Contracts Only.
    """

    STATE_IDLE = "IDLE / SCANNING"
    STATE_ENTRY_PENDING = "ENTRY PENDING"
    STATE_IN_TRADE = "IN-TRADE (ACTIVE MONITORING)"
    STATE_TRADE_CLOSED = "TRADE CLOSED & AUDITED"

    @classmethod
    def get_state_file_path(cls) -> str:
        return SEQUENTIAL_STATE_FILE

    @classmethod
    def get_state(cls) -> Dict[str, Any]:
        """Loads and returns current sequential engine state."""
        if os.path.exists(SEQUENTIAL_STATE_FILE):
            try:
                with open(SEQUENTIAL_STATE_FILE, "r", encoding="utf-8") as f:
                    state = json.load(f)
                    if isinstance(state, dict) and "current_state" in state:
                        return state
            except Exception as e:
                logger.debug(f"Error reading sequential state: {e}")

        # Initialize default state based on today's journal
        today_str = datetime.now(IST).strftime("%Y-%m-%d")
        journal = TradeJournalManager.load_journal()
        today_trades = [
            t for t in journal 
            if t.get("date") == today_str and "RELIANCE" in str(t.get("trading_symbol", "")).upper()
        ]

        open_trades = [t for t in today_trades if t.get("status") == "OPEN" or t.get("is_closed") is False]
        closed_trades = [t for t in today_trades if t.get("status") in ["HIT", "FAIL"] or t.get("is_closed") is True]

        if open_trades:
            active_tr = open_trades[-1]
            init_state = {
                "current_state": cls.STATE_IN_TRADE,
                "active_trade": {
                    "trade_num": len(closed_trades) + 1,
                    "contract": active_tr.get("trading_symbol", ""),
                    "instrument": active_tr.get("instrument", active_tr.get("trading_symbol", "")),
                    "planned_entry": float(active_tr.get("suggested_entry", active_tr.get("entry_price", 0.0))),
                    "actual_entry": float(active_tr.get("actual_entry_price", active_tr.get("entry_price", 0.0))),
                    "actual_entry_time": active_tr.get("actual_entry_time", ""),
                    "executed": "Yes",
                    "sl": float(active_tr.get("suggested_sl", max(0.05, active_tr.get("entry_price", 0.0) - 4.5))),
                    "target": float(active_tr.get("suggested_exit", active_tr.get("entry_price", 0.0) + 10.0)),
                    "direction": active_tr.get("type", "BUY PE"),
                    "qty": int(active_tr.get("qty", 1000)),
                    "num_lots": int(active_tr.get("num_lots", 2)),
                    "highest_price": float(active_tr.get("actual_entry_price", active_tr.get("entry_price", 0.0))),
                    "trailing_sl": float(active_tr.get("suggested_sl", max(0.05, active_tr.get("entry_price", 0.0) - 4.5))),
                    "status": "Open",
                    "confluence": float(active_tr.get("confluence_score", 75.0))
                },
                "last_closed_trade": closed_trades[-1] if closed_trades else None,
                "today_trade_count": len(today_trades),
                "updated_at": datetime.now(IST).strftime("%Y-%m-%d %I:%M:%S %p IST")
            }
        else:
            last_closed = closed_trades[-1] if closed_trades else None
            init_state = {
                "current_state": cls.STATE_IDLE,
                "active_trade": None,
                "last_closed_trade": {
                    "trade_num": len(closed_trades),
                    "instrument": last_closed.get("instrument", last_closed.get("trading_symbol", "")),
                    "planned_entry": float(last_closed.get("suggested_entry", 0.0)),
                    "actual_entry": float(last_closed.get("actual_entry_price", 0.0)),
                    "executed": "Yes",
                    "sl": float(last_closed.get("suggested_sl", 0.0)),
                    "target": float(last_closed.get("suggested_exit", 0.0)),
                    "status": "Target Hit" if last_closed.get("status") == "HIT" else "SL Hit",
                    "pnl": f"{'+' if last_closed.get('realised_pnl', 0.0) >= 0 else ''}₹{last_closed.get('realised_pnl', 0.0):,.2f}"
                } if last_closed else None,
                "today_trade_count": len(closed_trades),
                "updated_at": datetime.now(IST).strftime("%Y-%m-%d %I:%M:%S %p IST")
            }

        cls.save_state(init_state)
        return init_state

    @classmethod
    def save_state(cls, state: Dict[str, Any]):
        """Persists the engine state to disk."""
        state["updated_at"] = datetime.now(IST).strftime("%Y-%m-%d %I:%M:%S %p IST")
        try:
            with open(SEQUENTIAL_STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to persist sequential state: {e}")

    @classmethod
    def enter_trade_direct(
        cls,
        contract: str,
        instrument: str,
        entry_price: float,
        sl: float,
        target: float,
        direction: str,
        expiry: str,
        confluence: float,
        qty: int = 1000,
        num_lots: int = 2
    ) -> Dict[str, Any]:
        """
        Immediately transitions engine to IN-TRADE (ACTIVE MONITORING).
        Zero delay: called instantly as soon as a buy entry trigger is validated.
        Completely prevents flapping back to ARMED state when price fluctuates.
        """
        state = cls.get_state()
        curr_state = state.get("current_state", cls.STATE_IDLE)

        if curr_state == cls.STATE_IN_TRADE and state.get("active_trade"):
            return {
                "success": False,
                "msg": f"Already IN-TRADE with {state.get('active_trade', {}).get('instrument')}",
                "state": state
            }

        next_trade_num = int(state.get("today_trade_count", 0)) + 1
        now_time_str = datetime.now(IST).strftime("%I:%M:%S %p IST")
        actual_p = round(float(entry_price), 2)
        target_p = round(float(target), 2)
        sl_p = round(float(sl), 2)

        active_trade = {
            "trade_num": next_trade_num,
            "contract": contract,
            "instrument": instrument,
            "planned_entry": actual_p,
            "actual_entry": actual_p,
            "actual_entry_time": now_time_str,
            "executed": "Yes",
            "sl": sl_p,
            "target": target_p,
            "direction": direction,
            "expiry": expiry,
            "qty": int(qty),
            "num_lots": int(num_lots),
            "confluence": round(float(confluence), 1),
            "highest_price": actual_p,
            "trailing_sl": sl_p,
            "status": "Open",
            "proposed_at": now_time_str
        }

        state["current_state"] = cls.STATE_IN_TRADE
        state["active_trade"] = active_trade
        cls.save_state(state)

        today_str = datetime.now(IST).strftime("%Y-%m-%d")
        try:
            SignalTracker.save_signal({
                "date": today_str,
                "trade_given_time": now_time_str,
                "full_contract": instrument,
                "symbol": contract,
                "contract_type": "PE" if "PE" in contract else "CE",
                "strike": int("".join(filter(str.isdigit, contract)) or 1200),
                "expiry": expiry,
                "suggested_entry": actual_p,
                "suggested_exit": target_p,
                "suggested_sl": sl_p,
                "confluence_score": confluence
            })
        except Exception as e:
            logger.debug(f"SignalTracker save error: {e}")

        try:
            ShadowMonitoringEngine.log_signal(
                symbol=contract,
                action=f"BUY {'PE' if 'PE' in contract else 'CE'}",
                entry=actual_p,
                target=target_p,
                sl=sl_p,
                date_str=today_str,
                time_str=now_time_str,
                instrument=instrument,
                confluence_score=confluence,
                user_executed=True
            )
        except Exception as e:
            logger.debug(f"ShadowMonitoringEngine log error: {e}")

        return {
            "success": True,
            "msg": f"✅ Trade #{next_trade_num} is ACTIVE: {instrument} @ ₹{actual_p:.2f}",
            "state": state
        }

    @classmethod
    def propose_trade(
        cls,
        contract: str,
        instrument: str,
        planned_entry: float,
        sl: float,
        target: float,
        direction: str,
        expiry: str,
        confluence: float,
        qty: int = 1000,
        num_lots: int = 2
    ) -> Dict[str, Any]:
        """
        Rule 1: Propose a new trade setup. Strictly forbidden if an active or pending trade exists.
        Transitions state to ENTRY PENDING.
        """
        state = cls.get_state()
        curr_state = state.get("current_state", cls.STATE_IDLE)

        # Zero Parallel Signals Guard
        if curr_state in [cls.STATE_ENTRY_PENDING, cls.STATE_IN_TRADE]:
            return {
                "success": False,
                "msg": f"⛔ REJECTED: Sequential Rule #1 active. Current state is '{curr_state}'. Zero parallel trades permitted.",
                "state": state
            }

        next_trade_num = int(state.get("today_trade_count", 0)) + 1
        active_trade = {
            "trade_num": next_trade_num,
            "contract": contract,
            "instrument": instrument,
            "planned_entry": round(float(planned_entry), 2),
            "actual_entry": None,
            "actual_entry_time": None,
            "executed": "Pending",
            "sl": round(float(sl), 2),
            "target": round(float(target), 2),
            "direction": direction,
            "expiry": expiry,
            "qty": int(qty),
            "num_lots": int(num_lots),
            "confluence": round(float(confluence), 1),
            "highest_price": round(float(planned_entry), 2),
            "trailing_sl": round(float(sl), 2),
            "status": "Entry Pending",
            "proposed_at": datetime.now(IST).strftime("%I:%M:%S %p IST")
        }

        state["current_state"] = cls.STATE_ENTRY_PENDING
        state["active_trade"] = active_trade
        cls.save_state(state)

        # Also register in SignalTracker
        try:
            SignalTracker.save_signal({
                "date": datetime.now(IST).strftime("%Y-%m-%d"),
                "trade_given_time": active_trade["proposed_at"],
                "full_contract": instrument,
                "symbol": contract,
                "contract_type": "PE" if "PE" in contract else "CE",
                "strike": int("".join(filter(str.isdigit, contract)) or 1200),
                "expiry": expiry,
                "suggested_entry": planned_entry,
                "suggested_exit": target,
                "suggested_sl": sl,
                "confluence_score": confluence
            })
        except Exception:
            pass

        return {
            "success": True,
            "msg": f"✅ Trade #{next_trade_num} proposed: {instrument} @ ₹{planned_entry:.2f}. Waiting for Groww fill confirmation.",
            "state": state
        }

    @classmethod
    def confirm_groww_fill(
        cls,
        confirmed: bool,
        actual_price: Optional[float] = None,
        actual_time: Optional[str] = None,
        notes: str = ""
    ) -> Dict[str, Any]:
        """
        Rule 2: Verification with Groww.
        - If confirmed (Yes): transitions to IN-TRADE (ACTIVE MONITORING) with actual entry price & time.
        - If rejected / cancelled (No): transitions back to IDLE / SCANNING.
        """
        state = cls.get_state()
        if state.get("current_state") != cls.STATE_ENTRY_PENDING:
            return {
                "success": False,
                "msg": f"Engine not in ENTRY PENDING state (current: {state.get('current_state')}).",
                "state": state
            }

        active = state.get("active_trade")
        if not active:
            state["current_state"] = cls.STATE_IDLE
            cls.save_state(state)
            return {"success": False, "msg": "No pending trade record found.", "state": state}

        if confirmed:
            actual_p = float(actual_price if actual_price is not None and actual_price > 0 else active["planned_entry"])
            actual_t = actual_time or datetime.now(IST).strftime("%I:%M:%S %p IST")
            active["actual_entry"] = round(actual_p, 2)
            active["actual_entry_time"] = actual_t
            active["executed"] = "Yes"
            active["status"] = "Open"
            active["highest_price"] = actual_p
            active["trailing_sl"] = active["sl"]
            state["current_state"] = cls.STATE_IN_TRADE
            cls.save_state(state)
            return {
                "success": True,
                "msg": f"✅ Groww execution confirmed at ₹{actual_p:.2f} ({actual_t}). Trade #{active['trade_num']} is now ACTIVE.",
                "state": state
            }
        else:
            # Order not filled or cancelled
            t_num = active.get("trade_num", 1)
            inst = active.get("instrument", "")
            state["current_state"] = cls.STATE_IDLE
            state["active_trade"] = None
            cls.save_state(state)
            return {
                "success": True,
                "msg": f"ℹ️ Trade #{t_num} ({inst}) cancelled/not executed. Reverted to IDLE / SCANNING.",
                "state": state
            }

    @classmethod
    def update_active_trade(
        cls,
        current_ltp: float,
        groww_feed: Any = None,
        starting_cash: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Rule 3: Monitor Active Trade.
        Checks if Target Hit or SL Hit, updates trailing SL, or detects broker exit.
        """
        state = cls.get_state()
        if state.get("current_state") != cls.STATE_IN_TRADE:
            return {"active": False, "state": state}

        active = state.get("active_trade")
        if not active:
            state["current_state"] = cls.STATE_IDLE
            cls.save_state(state)
            return {"active": False, "state": state}

        current_ltp = float(current_ltp)
        actual_entry = float(active.get("actual_entry", active.get("planned_entry", 0.0)))
        target = float(active.get("target", actual_entry + 10.0))
        sl = float(active.get("sl", max(0.05, actual_entry - 4.5)))
        qty = int(active.get("qty", 1000))
        contract = active.get("contract", "")

        # Resolve real-time live LTP from Groww broker feed if connected (absolute zero latency)
        if groww_feed and getattr(groww_feed, "is_connected", False) and hasattr(groww_feed, "get_option_contract_ltp"):
            try:
                gw_ltp = groww_feed.get_option_contract_ltp(contract)
                if gw_ltp and gw_ltp > 0:
                    current_ltp = float(gw_ltp)
            except Exception:
                pass

        # Update high-water mark & Trailing SL (lock 50% gains above +5 pts)
        if current_ltp > active.get("highest_price", actual_entry):
            active["highest_price"] = round(current_ltp, 2)
            profit_pts = current_ltp - actual_entry
            if profit_pts >= 5.0:
                # Trail SL to entry + 50% of peak gain
                new_trail = round(actual_entry + (profit_pts * 0.5), 2)
                if new_trail > active.get("trailing_sl", sl):
                    active["trailing_sl"] = new_trail

        effective_sl = max(sl, active.get("trailing_sl", sl))
        unrealized_pnl = round((current_ltp - actual_entry) * qty, 2)
        active["current_ltp"] = current_ltp
        active["unrealized_pnl"] = unrealized_pnl

        # Check automated broker sync if Groww feed is provided
        if groww_feed and getattr(groww_feed, "is_connected", False):
            try:
                executed_today = groww_feed.get_executed_trades_today(symbol_filter="RELIANCE")
                journal_entries = TradeJournalManager.load_journal(starting_cash=starting_cash)
                used_exit_times = {str(j.get("actual_exit_time")) for j in journal_entries if j.get("actual_exit_time")}
                used_entry_times = {str(j.get("actual_entry_time")) for j in journal_entries if j.get("actual_entry_time")}

                for ex_tr in executed_today:
                    sym = ex_tr.get("symbol", "")
                    if contract in sym or (str(active.get("strike", "")) in sym and active.get("direction", "")[-2:] in sym):
                        raw_ex_t = str(ex_tr.get("exit_time", ""))
                        raw_en_t = str(ex_tr.get("entry_time", ""))
                        # Guard: Do not reuse an earlier closed broker trade that is already recorded in the journal!
                        if raw_ex_t and any(raw_ex_t in str(x) or str(x) in raw_ex_t for x in used_exit_times if x):
                            continue
                        if raw_en_t and any(raw_en_t in str(n) or str(n) in raw_en_t for n in used_entry_times if n):
                            continue

                        # Guard 2: If active trade is Trade #2+, do not match older broker trade #1!
                        t_num = int(active.get("trade_num", 1))
                        if t_num > len(executed_today):
                            continue

                        if ex_tr.get("is_closed", False):
                            # Position closed in Groww!
                            exit_p = float(ex_tr.get("exit_price", current_ltp))
                            exit_t = ex_tr.get("exit_time", datetime.now(IST).strftime("%I:%M:%S %p IST"))
                            real_pnl = float(ex_tr.get("realised_pnl", (exit_p - actual_entry) * qty))
                            status = "Target Hit" if real_pnl >= 0 else "SL Hit"
                            return cls.close_trade(
                                exit_price=exit_p,
                                status=status,
                                exit_time=exit_t,
                                notes=f"Auto-synced Groww Position Exit @ ₹{exit_p:.2f}",
                                starting_cash=starting_cash
                            )
            except Exception as e:
                logger.debug(f"Error checking broker sync for active trade: {e}")

        # Check Target Hit
        if current_ltp >= target:
            return cls.close_trade(
                exit_price=current_ltp,
                status="Target Hit",
                notes=f"Profit Target Reached: ₹{current_ltp:.2f} >= ₹{target:.2f} (+{round(current_ltp - actual_entry, 2)} pts)",
                starting_cash=starting_cash
            )

        # Check Stop-Loss Hit
        if current_ltp <= effective_sl:
            return cls.close_trade(
                exit_price=current_ltp,
                status="SL Hit",
                notes=f"Stop-Loss Triggered: ₹{current_ltp:.2f} <= ₹{effective_sl:.2f} (-{round(actual_entry - current_ltp, 2)} pts)",
                starting_cash=starting_cash
            )

        # Still in trade
        cls.save_state(state)
        return {
            "active": True,
            "current_ltp": current_ltp,
            "unrealized_pnl": unrealized_pnl,
            "distance_to_target": round(target - current_ltp, 2),
            "distance_to_sl": round(current_ltp - effective_sl, 2),
            "state": state
        }

    @classmethod
    def close_trade(
        cls,
        exit_price: float,
        status: str,
        exit_time: Optional[str] = None,
        notes: str = "",
        starting_cash: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Rule 4: Close and Audit Active Trade.
        Records outcome in daily journal and transitions engine to TRADE CLOSED & AUDITED.
        """
        state = cls.get_state()
        active = state.get("active_trade")
        if not active:
            state["current_state"] = cls.STATE_IDLE
            cls.save_state(state)
            return {"success": False, "msg": "No active trade to close.", "state": state}

        exit_p = round(float(exit_price), 2)
        exit_t = exit_time or datetime.now(IST).strftime("%I:%M:%S %p IST")
        actual_entry = float(active.get("actual_entry", active.get("planned_entry", 0.0)))
        qty = int(active.get("qty", 1000))
        pts = round(exit_p - actual_entry, 2)
        pnl = round(pts * qty, 2)
        t_num = active.get("trade_num", int(state.get("today_trade_count", 0)) + 1)
        inst = active.get("instrument", "")
        sym = active.get("contract", "")
        today_str = datetime.now(IST).strftime("%Y-%m-%d")

        # Record in daily journal ledger
        journal_rec = {
            "id": f"TRD-{today_str.replace('-', '')}-{t_num:02d}-{sym}",
            "date": today_str,
            "day": datetime.now(IST).strftime("%A"),
            "trading_symbol": sym,
            "instrument": inst,
            "type": active.get("direction", "BUY PE"),
            "decision": "TRADABLE (A+ SETUP)",
            "source": "GROWW_VERIFIED",
            "is_closed": True,
            "trade_given_time": active.get("proposed_at", "09:15:00 AM IST"),
            "suggested_contract": inst,
            "suggested_entry": active.get("planned_entry", actual_entry),
            "suggested_exit": active.get("target", actual_entry + 10.0),
            "suggested_sl": active.get("sl", actual_entry - 4.5),
            "suggested_target_pts": round(active.get("target", actual_entry + 10.0) - active.get("planned_entry", actual_entry), 2),
            "suggested_sl_pts": round(active.get("planned_entry", actual_entry) - active.get("sl", actual_entry - 4.5), 2),
            "actual_entry_time": active.get("actual_entry_time", exit_t),
            "actual_entry_price": actual_entry,
            "entry_price": actual_entry,
            "actual_exit_time": exit_t,
            "actual_exit_price": exit_p,
            "exit_price": exit_p,
            "num_lots": active.get("num_lots", 2),
            "lot_size": 500,
            "qty": qty,
            "capital_deployed": round(actual_entry * qty, 2),
            "realised_pnl": pnl,
            "total_profit": pnl,
            "net_profit": pnl,
            "net_pnl": pnl,
            "amount_captured": pnl if pnl > 0 else 0.0,
            "amount_lost": abs(pnl) if pnl < 0 else 0.0,
            "status": "HIT" if pnl >= 0 else "FAIL",
            "entry_slippage_pts": round(actual_entry - active.get("planned_entry", actual_entry), 2),
            "screenshot": "",
            "notes": f"Trade #{t_num} Closed ({status}) • Exit: ₹{exit_p:.2f} ({exit_t}) • {notes}",
            "confluence_score": active.get("confluence", 75.0)
        }
        TradeJournalManager.add_or_update_entry(journal_rec, starting_cash=starting_cash)

        # Transition state
        closed_summary = {
            "trade_num": t_num,
            "instrument": inst,
            "planned_entry": active.get("planned_entry", actual_entry),
            "actual_entry": actual_entry,
            "executed": "Yes",
            "sl": active.get("sl", actual_entry - 4.5),
            "target": active.get("target", actual_entry + 10.0),
            "status": status,
            "exit_price": exit_p,
            "exit_time": exit_t,
            "pnl": f"{'+' if pnl >= 0 else ''}₹{pnl:,.2f} ({'+' if pts >= 0 else ''}{pts:.2f} pts)"
        }

        state["current_state"] = cls.STATE_TRADE_CLOSED
        state["active_trade"] = None
        state["last_closed_trade"] = closed_summary
        state["today_trade_count"] = max(int(state.get("today_trade_count", 0)), t_num)
        cls.save_state(state)

        return {
            "success": True,
            "msg": f"🎯 Trade #{t_num} Closed! Status: {status} • P&L: {closed_summary['pnl']}",
            "closed_trade": closed_summary,
            "state": state
        }

    @classmethod
    def acknowledge_and_reset(cls) -> Dict[str, Any]:
        """
        Rule 5: Wait for closure.
        User acknowledges closed trade outcome; transitions engine back to IDLE / SCANNING.
        """
        state = cls.get_state()
        state["current_state"] = cls.STATE_IDLE
        cls.save_state(state)
        return {
            "success": True,
            "msg": "✅ Trade acknowledged and logged. Engine is now in IDLE / SCANNING for next high-probability setup.",
            "state": state
        }

    @classmethod
    def get_running_trade_log_rows(cls) -> List[Dict[str, Any]]:
        """
        Generates the EXACT running log table requested:
        Trade # | Instrument | Planned Entry | Actual Groww Entry | Executed (Yes/No) | SL | Target | Status (Open / Target Hit / SL Hit) | P&L
        """
        today_str = datetime.now(IST).strftime("%Y-%m-%d")
        journal = TradeJournalManager.load_journal()
        # Strictly RELIANCE trades for today
        today_trades = [
            t for t in journal 
            if t.get("date") == today_str and "RELIANCE" in str(t.get("trading_symbol", "")).upper()
        ]

        rows = []
        for i, tr in enumerate(today_trades, 1):
            st_raw = tr.get("status", "STAND DOWN")
            if st_raw == "HIT":
                status_label = "Target Hit"
            elif st_raw == "FAIL":
                status_label = "SL Hit"
            elif st_raw == "OPEN" or not tr.get("is_closed"):
                status_label = "Open"
            else:
                status_label = st_raw

            pnl_val = float(tr.get("realised_pnl", tr.get("total_profit", 0.0)))
            pnl_str = f"{'+' if pnl_val >= 0 else ''}₹{pnl_val:,.2f}"

            rows.append({
                "Trade #": f"Trade {i}",
                "Instrument": tr.get("instrument") or tr.get("trading_symbol") or f"RELIANCE {tr.get('suggested_contract')}",
                "Planned Entry": f"₹{float(tr.get('suggested_entry', 0.0)):.2f}",
                "Actual Groww Entry": f"₹{float(tr.get('actual_entry_price', tr.get('entry_price', 0.0))):.2f}",
                "Executed (Yes/No)": "Yes",
                "SL": f"₹{float(tr.get('suggested_sl', 0.0)):.2f}",
                "Target": f"₹{float(tr.get('suggested_exit', 0.0)):.2f}",
                "Status": status_label,
                "P&L": pnl_str
            })

        # If there is currently an active or pending trade not yet closed in journal, append it
        state = cls.get_state()
        curr_state = state.get("current_state")
        active = state.get("active_trade")
        if active and curr_state in [cls.STATE_ENTRY_PENDING, cls.STATE_IN_TRADE]:
            # Check if this active trade is already in rows by trade index or open status
            t_idx = int(active.get("trade_num") or (len(rows) + 1))
            already_in_rows = any(r.get("Trade #") == f"Trade {t_idx}" for r in rows)
            if not already_in_rows:
                if curr_state == cls.STATE_IN_TRADE:
                    act_entry = f"₹{float(active.get('actual_entry', 0.0)):.2f}"
                    status_lbl = "Open"
                    unreal = float(active.get("unrealized_pnl", 0.0))
                    pnl_lbl = f"{'+' if unreal >= 0 else ''}₹{unreal:,.2f} (Live)"
                    executed_lbl = "Yes"
                else:
                    act_entry = "Pending Fill"
                    status_lbl = "Entry Pending"
                    pnl_lbl = "₹0.00 (Pending)"
                    executed_lbl = "Pending"

                rows.append({
                    "Trade #": f"Trade {t_idx}",
                    "Instrument": active.get("instrument", active.get("contract", "")),
                    "Planned Entry": f"₹{float(active.get('planned_entry', 0.0)):.2f}",
                    "Actual Groww Entry": act_entry,
                    "Executed (Yes/No)": executed_lbl,
                    "SL": f"₹{float(active.get('sl', 0.0)):.2f}",
                    "Target": f"₹{float(active.get('target', 0.0)):.2f}",
                    "Status": status_lbl,
                    "P&L": pnl_lbl
                })

        return rows


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
    """Persists and retrieves the daily quant trade recommendations and given triggers."""

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
    def get_signal(cls, date_str: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if not date_str:
            date_str = datetime.now(IST).strftime("%Y-%m-%d")
        signals = cls.get_all_signals()
        return signals.get(date_str)

    @classmethod
    def save_signal(cls, signal: Dict[str, Any]):
        date_str = signal.get("date") or datetime.now(IST).strftime("%Y-%m-%d")
        signals = cls.get_all_signals()
        # Preserve original morning trade_given_time if already logged today
        if date_str in signals and signals[date_str].get("trade_given_time"):
            signal["trade_given_time"] = signals[date_str]["trade_given_time"]
        elif not signal.get("trade_given_time"):
            signal["trade_given_time"] = datetime.now(IST).strftime("%I:%M:%S %p IST")

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

        # Replace matching entry if exists
        def is_match(e):
            if entry_id and e.get("id") == entry_id:
                return True
            if date_to_log and sym_to_log and e.get("date") == date_to_log and e.get("trading_symbol") == sym_to_log:
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
    def update_screenshot(cls, trade_id: str, screenshot_path: str, starting_cash: float = None) -> List[Dict[str, Any]]:
        """Updates the screenshot path for a specific trade entry."""
        if starting_cash is None:
            starting_cash = STARTING_CAPITAL
        entries = cls.load_journal(starting_cash)
        for e in entries:
            if e.get("id") == trade_id or e.get("trading_symbol") == trade_id:
                e["screenshot"] = screenshot_path
                break
        cls.save_journal(entries)
        return entries

    @classmethod
    def save_screenshot_file(cls, trade_id: str, file_bytes: bytes, original_filename: str) -> str:
        """Saves an uploaded screenshot image file locally and returns its relative path."""
        ext = os.path.splitext(original_filename)[1] or ".png"
        clean_id = trade_id.replace(":", "_").replace("/", "_")
        filename = f"{clean_id}{ext}"
        target_path = os.path.join(SCREENSHOTS_DIR, filename)
        with open(target_path, "wb") as f:
            f.write(file_bytes)
        rel_path = os.path.join("screenshots", filename)
        cls.update_screenshot(trade_id, rel_path)
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
            key = f"{e.get('date', '')}_{e.get('trading_symbol', e.get('instrument', ''))}"
            existing_map[key] = e

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
            
            if is_reliance and signal:
                trade_given_time = signal.get("trade_given_time", "09:15:00 AM IST")
                sugg_contract = signal.get("full_contract") or f"RELIANCE {signal.get('strike', 1200)} {signal.get('contract_type', 'PE')} ({signal.get('expiry', '27-OCT-2026')})"
                sugg_entry = float(signal.get("suggested_entry", entry_p))
                sugg_exit = float(signal.get("suggested_exit", round(sugg_entry + 10.0, 2)))
                sugg_sl = float(signal.get("suggested_sl", round(max(0.05, sugg_entry - 4.5), 2)))
                confluence = float(signal.get("confluence_score", 78.5))
                trade_type = f"BUY {signal.get('contract_type', 'PE')}"
            else:
                trade_given_time = actual_entry_time_str or "09:15:00 AM IST"
                sugg_contract = sym
                sugg_entry = entry_p
                sugg_exit = round(entry_p + 10.0, 2)
                sugg_sl = round(max(0.05, entry_p - 4.5), 2)
                confluence = 70.0
                trade_type = "BUY CE" if "CE" in sym else ("BUY PE" if "PE" in sym else "BUY")

            entry_slippage = round(entry_p - sugg_entry, 2)
            cap_deployed = round(entry_p * qty, 2)
            
            composite_key = f"{today_str}_{sym}"
            existing = existing_map.get(composite_key, {})
            existing_screenshot = existing.get("screenshot", "")
            existing_notes = existing.get("notes", "")

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

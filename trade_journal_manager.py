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
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import pytz

IST = pytz.timezone("Asia/Kolkata")
logger = logging.getLogger(__name__)
from asset_config import get_asset_spec, resolve_symbol

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
            sym_canon = resolve_symbol(symbol)
            key = f"{date_str}_{sym_canon}"
            if key in signals:
                return signals[key]
            # Search if legacy key matches this specific symbol
            leg = signals.get(date_str)
            if leg and isinstance(leg, dict) and resolve_symbol(leg.get("symbol", "")) == sym_canon:
                return leg
            return None
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
        symbol = resolve_symbol(signal.get("symbol") or "RELIANCE")
        signal["symbol"] = symbol
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
        if date_str not in signals or resolve_symbol(signals[date_str].get("symbol", "")) == symbol:
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
        spec_entry = get_asset_spec(symbol=e.get("symbol"), contract=e.get("trading_symbol") or e.get("instrument"))
        lot_sz = int(e.get("lot_size") or spec_entry.lot_size)
        qty = int(e.get("qty", lot_sz))
        if qty <= 0:
            qty = lot_sz
        num_lots = max(1, round(qty / lot_sz)) if lot_sz > 0 else 1
        e["num_lots"] = e.get("num_lots", num_lots)
        e["lot_size"] = lot_sz
        e["qty"] = qty
        
        # Realized net P&L directly from Groww execution or captured/lost
        if "realised_pnl" in e and e["realised_pnl"] is not None:
            net = float(e["realised_pnl"])
        elif "net_profit" in e and e["net_profit"] is not None:
            net = float(e["net_profit"])
        elif e.get("status") == "HIT":
            def_cap = round(spec_entry.target_pts * qty, 2)
            net = float(e.get("amount_captured", def_cap))
        elif e.get("status") == "FAIL":
            def_lost = round(spec_entry.sl_pts * qty, 2)
            net = -float(e.get("amount_lost", def_lost))
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

        # Gap 4: Live Slippage Tracking & Execution Variance Analysis
        planned_ep = float(e.get("suggested_entry", ep))
        actual_ep = ep
        entry_slippage_pts = round(actual_ep - planned_ep, 2) if planned_ep > 0 else 0.0

        planned_xp = float(e.get("suggested_exit", 0.0))
        actual_xp = float(e.get("exit_price", e.get("actual_exit_price", 0.0)))
        exit_slippage_pts = round(planned_xp - actual_xp, 2) if (planned_xp > 0 and actual_xp > 0) else 0.0

        total_slippage_pts = round(entry_slippage_pts + exit_slippage_pts, 2)
        total_slippage_drag = round(total_slippage_pts * qty, 2)

        e["planned_entry_price"] = planned_ep
        e["actual_fill_price"] = actual_ep
        e["entry_slippage_pts"] = entry_slippage_pts
        e["planned_exit_price"] = planned_xp
        e["actual_exit_price"] = actual_xp
        e["exit_slippage_pts"] = exit_slippage_pts
        e["total_slippage_pts"] = total_slippage_pts
        e["total_slippage_drag_rupees"] = total_slippage_drag

        # Estimate statutory charges (STT, GST, Exchange fees, SEBI, Brokerage configured per AssetSpec)
        statutory_charges = round(spec_entry.estimated_tax_per_lot * num_lots, 2) if ep > 0 else 0.0
        net_after_charges = round(net - statutory_charges, 2) if e.get("is_closed") else net
        e["estimated_statutory_charges"] = statutory_charges
        e["net_pnl_after_charges"] = net_after_charges

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
    def _load_raw_entries(cls) -> List[Dict[str, Any]]:
        """Loads all raw journal records from disk without symbol filtering."""
        if not os.path.exists(JOURNAL_FILE):
            cls.save_journal([])
            return []
        try:
            with open(JOURNAL_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
            cls.save_journal([])
            return []
        except Exception:
            cls.save_journal([])
            return []

    @classmethod
    def load_journal(cls, starting_cash: float = None, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Loads journal from JSON file. Returns clean list filtered by symbol if provided."""
        raw_entries = cls._load_raw_entries()
        if not raw_entries:
            return []

        if symbol:
            sym_canon = resolve_symbol(symbol)
            if starting_cash is None or starting_cash <= 0:
                starting_cash = get_asset_spec(sym_canon).total_capital
            sym_clean = "ADANI" if sym_canon == "ADANIENT" else sym_canon
            matching = [
                e for e in raw_entries
                if sym_clean in str(e.get("trading_symbol", "")).upper()
                or sym_clean in str(e.get("instrument", "")).upper()
                or str(e.get("symbol", "")).upper() == sym_canon
            ]
            if len(matching) > 0:
                return recalculate_journal(matching, starting_cash)
            return []
        else:
            if starting_cash is None or starting_cash <= 0:
                starting_cash = STARTING_CAPITAL
            return recalculate_journal(raw_entries, starting_cash)

    @classmethod
    def save_journal(cls, entries: List[Dict[str, Any]]):
        """Saves journal records to JSON file."""
        with open(JOURNAL_FILE, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2)

    @classmethod
    def add_or_update_entry(cls, new_entry: Dict[str, Any], starting_cash: float = None) -> List[Dict[str, Any]]:
        """Adds a new daily trade record or updates existing trade across all assets."""
        if starting_cash is None or starting_cash <= 0:
            e_sym = resolve_symbol(new_entry.get("symbol") or new_entry.get("trading_symbol") or new_entry.get("instrument"))
            starting_cash = get_asset_spec(e_sym).total_capital
        # Load raw records across all symbols so we never delete other assets!
        entries = cls._load_raw_entries()
        entry_id = new_entry.get("id")

        # Replace matching entry if exists by unique ID
        def is_match(e):
            if entry_id and e.get("id") == entry_id:
                return True
            return False

        entries = [e for e in entries if not is_match(e)]
        entries.append(new_entry)
        
        # Partition and recalculate cleanly per symbol to maintain independent capital & cumulative profit ledgers
        by_symbol: Dict[str, List[Dict[str, Any]]] = {}
        for e in entries:
            sym_c = resolve_symbol(e.get("symbol") or e.get("trading_symbol") or e.get("instrument"))
            by_symbol.setdefault(sym_c, []).append(e)
        
        all_recalculated = []
        for sym_c, sym_entries in by_symbol.items():
            sym_starting = get_asset_spec(sym_c).total_capital
            all_recalculated.extend(recalculate_journal(sym_entries, sym_starting))
            
        all_recalculated.sort(key=lambda x: (x.get("date", ""), x.get("actual_entry_time", "")))
        cls.save_journal(all_recalculated)
        return all_recalculated

    @classmethod
    def delete_entry(cls, entry_id: str, starting_cash: float = None) -> List[Dict[str, Any]]:
        """Deletes trade record by ID or date across all assets."""
        entries = cls._load_raw_entries()
        entries = [e for e in entries if e.get("id") != entry_id and e.get("date") != entry_id]
        
        by_symbol: Dict[str, List[Dict[str, Any]]] = {}
        for e in entries:
            sym_c = resolve_symbol(e.get("symbol") or e.get("trading_symbol") or e.get("instrument"))
            by_symbol.setdefault(sym_c, []).append(e)
            
        all_recalculated = []
        for sym_c, sym_entries in by_symbol.items():
            sym_starting = get_asset_spec(sym_c).total_capital
            all_recalculated.extend(recalculate_journal(sym_entries, sym_starting))
            
        all_recalculated.sort(key=lambda x: (x.get("date", ""), x.get("actual_entry_time", "")))
        cls.save_journal(all_recalculated)
        return all_recalculated

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
        starting_cash: float = None,
        symbol_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Automates cross-verification between the trade given by the system and actual trades executed on Groww.
        Strict rule: ONLY trades executed in Groww broker account are added / updated in the ledger!
        """
        sym_canon = resolve_symbol(symbol_filter)
        sym_kw = "ADANI" if sym_canon == "ADANIENT" else sym_canon
        if starting_cash is None or starting_cash <= 0:
            starting_cash = get_asset_spec(sym_canon).total_capital

        current_entries = cls._load_raw_entries()
        today_str = datetime.now(IST).strftime("%Y-%m-%d")
        today_day = datetime.now(IST).strftime("%A")

        # Deduplicate existing entries strictly by unique trade ID
        unique_entries = {}
        for e in current_entries:
            eid = e.get("id") or f"TRD-{e.get('date', today_str).replace('-', '')}-01-{e.get('trading_symbol', '')}"
            e["id"] = eid
            unique_entries[eid] = e
        
        # Load or use active signal for today
        signal = active_signal or SignalTracker.get_signal(today_str, symbol=symbol_filter) or {}

        for gt in groww_executed_trades:
            sym = gt.get("symbol", "")
            if not sym or sym_kw not in sym.upper():
                continue

            entry_p = float(gt.get("entry_price", 0.0))
            exit_p = float(gt.get("exit_price", 0.0))
            spec = get_asset_spec(sym or sym_kw)
            qty = int(gt.get("qty", spec.lot_size * spec.default_lots))
            is_closed = bool(gt.get("is_closed", False))
            realised_pnl = float(gt.get("realised_pnl", 0.0))
            if is_closed and realised_pnl == 0.0 and exit_p > 0 and entry_p > 0:
                realised_pnl = round((exit_p - entry_p) * qty, 2)
            
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

            is_target_scrip = sym_kw in sym.upper()

            # Find matching existing entry (by timestamp or contract + entry price)
            existing_match_id = None
            for eid, e in unique_entries.items():
                if e.get("date") != today_str:
                    continue
                # Match by timestamp if available
                e_en_t = str(e.get("actual_entry_time", ""))
                if raw_entry_t and (raw_entry_t in e_en_t or e_en_t in raw_entry_t):
                    existing_match_id = eid
                    break
                # Match by symbol and entry price within tolerance
                if e.get("trading_symbol") == sym and abs(float(e.get("actual_entry_price", 0.0)) - entry_p) < 0.15:
                    existing_match_id = eid
                    break

            existing = unique_entries.get(existing_match_id, {}) if existing_match_id else {}
            existing_screenshot = existing.get("screenshot", "")
            existing_notes = existing.get("notes", "")

            # Strict Rule: If this trade was ALREADY cross-verified and stored in journal, KEEP ITS ORIGINAL GIVEN DETAILS!
            # Never overwrite a completed morning trade with an afternoon scan or different strike!
            spec_exec = get_asset_spec(symbol=sym_kw, contract=sym)
            if existing and existing.get("suggested_entry") is not None and existing.get("trade_given_time"):
                trade_given_time = existing["trade_given_time"]
                sugg_contract = existing.get("suggested_contract") or existing.get("instrument") or sym
                sugg_entry = float(existing["suggested_entry"])
                sugg_exit = float(existing.get("suggested_exit", round(sugg_entry + spec_exec.target_pts, 2)))
                sugg_sl = float(existing.get("suggested_sl", round(max(0.05, sugg_entry - spec_exec.sl_pts), 2)))
                confluence = float(existing.get("confluence_score", 78.5))
                trade_type = existing.get("type", "BUY PE" if "PE" in sym else "BUY CE")
            else:
                matched_signal = SignalTracker.find_matching_signal(symbol=sym, actual_entry_time=actual_entry_time_str, date_str=today_str)
                if matched_signal:
                    trade_given_time = matched_signal.get("trade_given_time", actual_entry_time_str)
                    from nse_data_fetcher import NSEIndiaFetcher
                    default_exp = NSEIndiaFetcher.resolve_dynamic_expiry_mandate(symbol=sym_kw)["selected_expiry"]
                    sugg_contract = matched_signal.get("full_contract") or f"{sym_kw} {matched_signal.get('strike', spec_exec.default_strike)} {matched_signal.get('contract_type', 'PE')} ({matched_signal.get('expiry', default_exp)})"
                    sugg_entry = float(matched_signal.get("suggested_entry", entry_p))
                    sugg_exit = float(matched_signal.get("suggested_exit", round(sugg_entry + spec_exec.target_pts, 2)))
                    sugg_sl = float(matched_signal.get("suggested_sl", round(max(0.05, sugg_entry - spec_exec.sl_pts), 2)))
                    confluence = float(matched_signal.get("confluence_score", 78.5))
                    trade_type = f"BUY {matched_signal.get('contract_type', 'PE' if 'PE' in sym else 'CE')}"
                else:
                    # No model recommendation preceded this execution -> Discretionary / User execution
                    trade_given_time = actual_entry_time_str or "09:15:00 AM IST"
                    sugg_contract = sym
                    sugg_entry = entry_p
                    sugg_exit = round(entry_p + spec_exec.target_pts, 2)
                    sugg_sl = round(max(0.05, entry_p - spec_exec.sl_pts), 2)
                    confluence = 75.0
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

            rec_id = existing_match_id or f"TRD-{today_str.replace('-', '')}-{len(unique_entries) + 1:02d}-{sym}"
            record = {
                "id": rec_id,
                "date": today_str,
                "day": today_day,
                "trading_symbol": sym,
                "instrument": sugg_contract,
                "type": trade_type,
                "decision": "TRADABLE (A+ SETUP)" if is_target_scrip else "DISCRETIONARY GROWW TRADE",
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
                "num_lots": max(1, round(qty / spec_exec.lot_size)) if spec_exec.lot_size > 0 else 1,
                "lot_size": spec_exec.lot_size,
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
            unique_entries[rec_id] = record

        all_updated = list(unique_entries.values())
        recalculated = recalculate_journal(all_updated, starting_cash)
        cls.save_journal(recalculated)
        return cls.load_journal(starting_cash=starting_cash, symbol=symbol_filter)

    @classmethod
    def sync_with_groww_executed_trades(
        cls,
        groww_feed: Any,
        starting_cash: Optional[float] = None,
        symbol_filter: Optional[str] = None
    ) -> int:
        """
        Fetches genuine executed trades from Groww broker API for today and reconciles them into the trade journal.
        Returns the count of synced/updated trades.
        """
        if not groww_feed or not getattr(groww_feed, "is_connected", False):
            return 0
        try:
            executed = groww_feed.get_executed_trades_today(symbol_filter=symbol_filter)
            if not executed:
                return 0
            cls.sync_groww_trades(executed, starting_cash=starting_cash, symbol_filter=symbol_filter)
            return len(executed)
        except Exception as e:
            logger.warning(f"Error syncing with Groww executed trades: {e}")
            return 0

    @classmethod
    def get_summary_kpi(cls, entries: List[Dict[str, Any]], today_strike_price: float = None, starting_cash: float = None, symbol: Optional[str] = None) -> Dict[str, Any]:
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
        
        # Today's required capital for configured lot count
        entry_sym = symbol
        if not entry_sym and entries:
            for e in entries:
                c = str(e.get("contract", "") or e.get("symbol", "") or e.get("trading_symbol", "") or e.get("instrument", ""))
                res = resolve_symbol(c)
                if res:
                    entry_sym = res
                    break
        entry_sym = resolve_symbol(entry_sym or "RELIANCE")
        spec = get_asset_spec(symbol=entry_sym)
        
        starting_capital = starting_cash if (starting_cash is not None and starting_cash > 0) else spec.total_capital
        total_cash = round(starting_capital + total_profit, 2)
        ref_prem = today_strike_price if (today_strike_price is not None and today_strike_price > 0) else spec.default_call_price
        today_2lot_capital = round(spec.default_lots * spec.lot_size * ref_prem, 2)
        
        win_rate = (len(hits) / len(traded_days) * 100.0) if len(traded_days) > 0 else 0.0
        profit_factor = (total_captured / total_lost) if total_lost > 0 else (total_captured if total_captured > 0 else 1.0)
        roi_pct = (total_profit / starting_capital) * 100.0 if starting_capital > 0 else 0.0
        
        avg_capital_deployed = round(sum(e.get("capital_deployed", 0.0) for e in traded_days) / len(traded_days), 2) if traded_days else 0.0
        
        # Gap 4: Slippage drag aggregation across executed trades
        all_slippages = [float(e.get("entry_slippage_pts", 0.0)) for e in traded_days if e.get("entry_slippage_pts") is not None]
        avg_entry_slippage = round(sum(all_slippages) / len(all_slippages), 2) if all_slippages else 0.0
        total_slippage_drag = round(sum(float(e.get("total_slippage_drag_rupees", 0.0)) for e in traded_days), 2)

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
            "stand_downs": len(stand_down_days),
            "avg_entry_slippage_pts": avg_entry_slippage,
            "total_slippage_drag_rupees": total_slippage_drag
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
    def load_records(cls, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        if os.path.exists(SHADOW_SIGNALS_FILE):
            try:
                with open(SHADOW_SIGNALS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        records = data
                    else:
                        records = cls._bootstrap_from_existing()
            except Exception as e:
                logger.debug(f"Error loading shadow signals log: {e}")
                records = cls._bootstrap_from_existing()
        else:
            records = cls._bootstrap_from_existing()

        if symbol:
            sym_canon = resolve_symbol(symbol)
            sym_kw = "ADANI" if sym_canon == "ADANIENT" else sym_canon
            return [
                r for r in records
                if sym_kw in str(r.get("symbol", "")).upper() or sym_kw in str(r.get("instrument", "")).upper()
            ]
        return records

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
                            spec_boot = get_asset_spec(contract=sym)
                            sugg_e = float(j.get("suggested_entry", j.get("entry_price", 30.0)))
                            sugg_t = float(j.get("suggested_exit", sugg_e + spec_boot.target_pts))
                            sugg_sl = float(j.get("suggested_sl", max(0.05, sugg_e - spec_boot.sl_pts)))
                            act_e = float(j.get("actual_entry_price", sugg_e))
                            act_x = float(j.get("actual_exit_price", sugg_t))
                            high_p = max(sugg_e, act_e, act_x, sugg_t)
                            low_p = min(sugg_e, act_e, act_x, sugg_sl)
                            status_raw = j.get("status", "HIT")
                            outcome = "Target Hit" if status_raw == "HIT" else ("Stop-Loss Hit" if status_raw == "FAIL" else "Active Monitoring")
                            has_verified_exec = bool(j.get("source") == "GROWW_VERIFIED" and (j.get("actual_entry_time") or j.get("screenshot")))
                            j_date = j.get("date") or datetime.now(IST).strftime("%Y-%m-%d")
                            rec = {
                                "id": j.get("id") or f"SIG-{j_date.replace('-', '')}-01-{sym}",
                                "timestamp": j.get("trade_given_time", "09:15:00 AM IST"),
                                "date": j_date,
                                "symbol": sym,
                                "instrument": j.get("instrument") or j.get("suggested_contract") or sym,
                                "action": j.get("type", "BUY PE" if "PE" in sym else "BUY CE"),
                                "entry": sugg_e,
                                "target": sugg_t,
                                "sl": sugg_sl,
                                "target_pts": round(sugg_t - sugg_e, 2),
                                "sl_pts": round(sugg_e - sugg_sl, 2),
                                "user_executed": bool(has_verified_exec),
                                "actual_entry_price": act_e if has_verified_exec else None,
                                "actual_entry_time": j.get("actual_entry_time", "") if has_verified_exec else "",
                                "actual_exit_price": act_x if has_verified_exec else None,
                                "actual_exit_time": j.get("actual_exit_time", "") if has_verified_exec else "",
                                "realised_pnl": float(j.get("realised_pnl", 0.0)) if has_verified_exec else 0.0,
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
        
        def _parse_mins(t_val) -> Optional[float]:
            if not t_val:
                return None
            t_str = str(t_val).strip()
            clean = t_str.replace("IST", "").strip()
            if "T" in clean:
                try:
                    t_part = clean.split("T")[1].replace("Z", "")
                    p = t_part.split(":")
                    return int(p[0]) * 60 + int(p[1]) + (float(p[2]) / 60.0 if len(p) > 2 else 0.0)
                except Exception:
                    pass
            for fmt in ["%I:%M:%S %p", "%I:%M %p", "%H:%M:%S", "%H:%M"]:
                try:
                    dt = datetime.strptime(clean, fmt)
                    return dt.hour * 60 + dt.minute + (dt.second / 60.0 if hasattr(dt, "second") else 0.0)
                except Exception:
                    pass
            return None

        time_mins = _parse_mins(time_str)
        target_canon = resolve_symbol(symbol)
        for r in records:
            r_sym_raw = str(r.get("symbol") or r.get("instrument") or "").strip()
            if not r_sym_raw:
                continue
            r_canon = resolve_symbol(r_sym_raw)
            if r.get("date") == date_str and r_canon == target_canon:
                if r.get("shadow_status") == "Active Monitoring":
                    return r
                r_mins = _parse_mins(r.get("timestamp"))
                if time_mins is not None and r_mins is not None and abs(time_mins - r_mins) < 15.0:
                    return r
                if r.get("timestamp") == time_str:
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
        - Cross-verifies executed broker fills with Groww to update user_executed (Strict 1-to-1 Chronological Verification).
        """
        records = cls.load_records()
        if not records:
            return []

        today_str = datetime.now(IST).strftime("%Y-%m-%d")
        now_dt = datetime.now(IST)
        now_time = now_dt.time()
        from datetime import time as time_type
        market_close = time_type(15, 30, 0)

        def _parse_time_minutes(t_val) -> Optional[float]:
            if not t_val:
                return None
            t_str = str(t_val).strip()
            clean = t_str.replace("IST", "").strip()
            if "T" in clean:
                try:
                    t_part = clean.split("T")[1].replace("Z", "")
                    p = t_part.split(":")
                    return int(p[0]) * 60 + int(p[1]) + (float(p[2]) / 60.0 if len(p) > 2 else 0.0)
                except Exception:
                    pass
            for fmt in ["%I:%M:%S %p", "%I:%M %p", "%H:%M:%S", "%H:%M"]:
                try:
                    dt = datetime.strptime(clean, fmt)
                    return dt.hour * 60 + dt.minute + (dt.second / 60.0 if hasattr(dt, "second") else 0.0)
                except Exception:
                    pass
            return None

        # 1. Collect verified executed trades for today from live Groww API and/or journal
        verified_executed_trades = []
        if groww_feed and getattr(groww_feed, "is_connected", False):
            try:
                gw_trades = groww_feed.get_executed_trades_today()
                verified_executed_trades = list(gw_trades)
            except Exception as e:
                logger.debug(f"Shadow check executed trades error: {e}")

        # If live Groww is disconnected or offline, fallback to today's verified journal trades
        if not verified_executed_trades:
            try:
                j_entries = TradeJournalManager.load_journal()
                for j in j_entries:
                    if j.get("date") == today_str and j.get("source") == "GROWW_VERIFIED" and (j.get("actual_entry_time") or j.get("screenshot")):
                        verified_executed_trades.append({
                            "symbol": j.get("trading_symbol", ""),
                            "is_closed": j.get("is_closed", True),
                            "entry_time": j.get("actual_entry_time", ""),
                            "exit_time": j.get("actual_exit_time", ""),
                            "entry_price": float(j.get("actual_entry_price", j.get("entry_price", 0.0))),
                            "exit_price": float(j.get("actual_exit_price", j.get("exit_price", 0.0))),
                            "realised_pnl": float(j.get("realised_pnl", 0.0))
                        })
            except Exception as e:
                logger.debug(f"Fallback journal executed trades error: {e}")

        updated_any = False
        claimed_trades = set()

        # Sort today records chronologically by timestamp so earlier signals claim earlier fills
        today_recs = [r for r in records if r.get("date") == today_str]
        today_recs.sort(key=lambda x: _parse_time_minutes(x.get("timestamp")) or 0.0)

        for rec in today_recs:
            sym = rec.get("symbol", "")
            rec_spec = get_asset_spec(sym)
            shadow_qty = int(rec.get("qty", rec_spec.lot_size * rec_spec.default_lots))
            entry = float(rec.get("entry", 30.0))
            target = float(rec.get("target", entry + rec_spec.target_pts))
            sl = float(rec.get("sl", entry - rec_spec.sl_pts))
            rec_mins = _parse_time_minutes(rec.get("timestamp"))

            # Auto-check user execution on Groww (Strict chronological 1-to-1 matching)
            matched_ex = None
            matched_idx = None
            for idx, ex_tr in enumerate(verified_executed_trades):
                if idx in claimed_trades:
                    continue
                ex_sym = ex_tr.get("symbol", "")
                if sym not in ex_sym and ex_sym not in sym:
                    continue

                ex_mins = _parse_time_minutes(ex_tr.get("entry_time"))
                if rec_mins is not None and ex_mins is not None:
                    # Clock tolerance: broker fill must not be earlier than signal generation time - 2 mins
                    if ex_mins < (rec_mins - 2.0):
                        continue
                    # Must be within 180 minutes of signal
                    if (ex_mins - rec_mins) > 180.0:
                        continue

                # Dynamic price tolerance scaled to asset volatility/breakout buffer
                ex_entry_p = float(ex_tr.get("entry_price", 0.0))
                price_tol = max(3.5, rec_spec.breakout_buffer * 1.5)
                if ex_entry_p > 0 and abs(ex_entry_p - entry) > price_tol:
                    continue

                matched_ex = ex_tr
                matched_idx = idx
                break

            if matched_ex is not None:
                claimed_trades.add(matched_idx)
                if not rec.get("user_executed"):
                    rec["user_executed"] = True
                    updated_any = True
                rec["actual_entry_price"] = float(matched_ex.get("entry_price", entry))
                rec["actual_entry_time"] = matched_ex.get("entry_time", "")
                if matched_ex.get("is_closed"):
                    rec["actual_exit_price"] = float(matched_ex.get("exit_price", entry))
                    rec["actual_exit_time"] = matched_ex.get("exit_time", "")
                    rec["realised_pnl"] = float(matched_ex.get("realised_pnl", 0.0))
                    updated_any = True
            else:
                # No matching Groww execution found!
                # If there is no uploaded screenshot proof, this signal was NOT executed by user in Groww!
                has_audit_screenshot = bool(rec.get("screenshot") or rec.get("screenshot_data_uri"))
                if not has_audit_screenshot:
                    if rec.get("user_executed") is True or rec.get("actual_entry_price") is not None:
                        rec["user_executed"] = False
                        rec["actual_entry_price"] = None
                        rec["actual_entry_time"] = ""
                        rec["actual_exit_price"] = None
                        rec["actual_exit_time"] = ""
                        rec["realised_pnl"] = 0.0
                        updated_any = True

            # Shadow Price Action Monitoring
            status = rec.get("shadow_status", "Active Monitoring")
            if status == "Active Monitoring":
                live_price = None
                contract_str = rec.get("instrument") or rec.get("contract") or sym
                if groww_feed:
                    try:
                        live_price = groww_feed.get_option_contract_ltp(contract_str, symbol=sym)
                    except Exception:
                        live_price = None

                # Sanity check: Option LTP cannot jump > 3.5x entry price or be an anomalous index/commodity quote
                if live_price is not None and live_price > 0:
                    if entry > 0 and live_price > (entry * 3.5):
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
                        rec["shadow_pnl"] = round(rec["shadow_pts"] * shadow_qty, 2)
                        updated_any = True
                    # Check Stop-Loss Hit
                    elif live_p <= sl:
                        rec["shadow_status"] = "Stop-Loss Hit"
                        rec["exit_price"] = round(sl, 2)
                        rec["exit_time"] = now_dt.strftime("%I:%M:%S %p IST")
                        rec["shadow_pts"] = round(sl - entry, 2)
                        rec["shadow_pnl"] = round(rec["shadow_pts"] * shadow_qty, 2)
                        updated_any = True
                    # Check EOD Exit (at 3:30 PM)
                    elif now_time >= market_close:
                        rec["shadow_status"] = "EOD Exit"
                        rec["exit_price"] = round(live_p, 2)
                        rec["exit_time"] = "03:30:00 PM IST"
                        rec["shadow_pts"] = round(live_p - entry, 2)
                        rec["shadow_pnl"] = round(rec["shadow_pts"] * shadow_qty, 2)
                        updated_any = True
                    else:
                        cur_pts = round(live_p - entry, 2)
                        rec["shadow_pts"] = cur_pts
                        rec["shadow_pnl"] = round(cur_pts * shadow_qty, 2)

                elif now_time >= market_close:
                    rec["shadow_status"] = "EOD Exit"
                    rec["exit_price"] = float(rec.get("current_price", entry))
                    rec["exit_time"] = "03:30:00 PM IST"
                    rec["shadow_pts"] = round(rec["exit_price"] - entry, 2)
                    rec["shadow_pnl"] = round(rec["shadow_pts"] * shadow_qty, 2)
                    updated_any = True

        # Check for any unclaimed Groww executed trades and make entry for them!
        for idx, ex_tr in enumerate(verified_executed_trades):
            if idx in claimed_trades:
                continue
            ex_sym = ex_tr.get("symbol", "")
            ex_time = ex_tr.get("entry_time", "")
            ex_price = float(ex_tr.get("entry_price", 0.0))
            is_closed = ex_tr.get("is_closed", False)
            exit_p = float(ex_tr.get("exit_price", 0.0))
            exit_t = ex_tr.get("exit_time", "")
            pnl = float(ex_tr.get("realised_pnl", 0.0))

            matched_signal = SignalTracker.find_matching_signal(symbol=ex_sym, actual_entry_time=ex_time, date_str=today_str)
            sugg_entry = float(matched_signal.get("suggested_entry", ex_price)) if matched_signal else ex_price
            sugg_target = float(matched_signal.get("suggested_exit", sugg_entry + 10.0)) if matched_signal else round(sugg_entry + 10.0, 2)
            sugg_sl = float(matched_signal.get("suggested_sl", max(0.05, sugg_entry - 4.5))) if matched_signal else round(max(0.05, sugg_entry - 4.5), 2)
            t_time = matched_signal.get("trade_given_time", ex_time) if matched_signal else ex_time

            new_rec = {
                "id": f"TRD-{today_str.replace('-', '')}-{len(records) + 1:02d}-{ex_sym}",
                "timestamp": t_time,
                "date": today_str,
                "symbol": ex_sym,
                "instrument": matched_signal.get("full_contract", ex_sym) if matched_signal else ex_sym,
                "action": "BUY PE" if "PE" in ex_sym else "BUY CE",
                "entry": sugg_entry,
                "target": sugg_target,
                "sl": sugg_sl,
                "target_pts": round(sugg_target - sugg_entry, 2),
                "sl_pts": round(sugg_entry - sugg_sl, 2),
                "user_executed": True,
                "actual_entry_price": ex_price,
                "actual_entry_time": ex_time,
                "actual_exit_price": exit_p if is_closed else None,
                "actual_exit_time": exit_t if is_closed else "",
                "realised_pnl": pnl if is_closed else 0.0,
                "screenshot": "",
                "screenshot_data_uri": "",
                "shadow_status": ("Target Hit" if pnl >= 0 else "Stop-Loss Hit") if is_closed else "Active Monitoring",
                "highest_price_reached": max(ex_price, exit_p) if is_closed else ex_price,
                "lowest_price_reached": min(ex_price, exit_p) if is_closed else ex_price,
                "current_price": exit_p if is_closed else ex_price,
                "exit_price": exit_p if is_closed else None,
                "exit_time": exit_t if is_closed else "",
                "shadow_pts": round(exit_p - sugg_entry, 2) if is_closed else 0.0,
                "shadow_pnl": pnl if is_closed else 0.0,
                "confluence_score": float(matched_signal.get("confluence_score", 78.0)) if matched_signal else 75.0,
                "notes": f"Verified Groww Execution • Buy ₹{ex_price:.2f}" + (f" -> Sell ₹{exit_p:.2f} • Realized P&L: ₹{pnl:+,.2f}" if is_closed else "")
            }
            records.append(new_rec)
            claimed_trades.add(idx)
            updated_any = True

        # Deduplicate records by unique key (id or date + symbol + timestamp)
        unique_recs = {}
        for r in records:
            key = r.get("id") or f"{r.get('date')}_{r.get('symbol')}_{r.get('timestamp')}"
            unique_recs[key] = r
        if len(unique_recs) != len(records):
            updated_any = True
        records = list(unique_recs.values())

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
    def get_records_by_date(cls, selected_date: Optional[str] = None, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        records = cls.load_records(symbol=symbol)
        def _get_sort_key(r):
            t_str = str(r.get("timestamp", ""))
            mins = 0.0
            try:
                clean = t_str.replace("IST", "").strip()
                dt = datetime.strptime(clean, "%I:%M:%S %p")
                mins = dt.hour * 60 + dt.minute + dt.second / 60.0
            except Exception:
                try:
                    dt = datetime.strptime(clean, "%I:%M %p")
                    mins = dt.hour * 60 + dt.minute
                except Exception:
                    pass
            return (r.get("date", ""), mins)

        if not selected_date or selected_date.upper() == "ALL":
            return sorted(records, key=_get_sort_key, reverse=True)
        return sorted(
            [r for r in records if r.get("date") == selected_date],
            key=_get_sort_key,
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
    Rule 6: Strictly Whitelisted High-Liquidity Contracts Only (RELIANCE / ADANIENT).
    """

    STATE_IDLE = "IDLE / SCANNING"
    STATE_ENTRY_PENDING = "ENTRY PENDING"
    STATE_IN_TRADE = "IN-TRADE (ACTIVE MONITORING)"
    STATE_TRADE_CLOSED = "TRADE CLOSED & AUDITED"

    @classmethod
    def get_state_file_path(cls, symbol: Optional[str] = None) -> str:
        sym = resolve_symbol(symbol=symbol)
        if sym == "RELIANCE":
            return SEQUENTIAL_STATE_FILE
        return os.path.join(BASE_DIR, f"sequential_trade_state_{sym}.json")

    @classmethod
    def get_state(cls, symbol: Optional[str] = None) -> Dict[str, Any]:
        """Loads and returns current sequential engine state for the specified symbol."""
        sym_kw = resolve_symbol(symbol=symbol)
        today_str = datetime.now(IST).strftime("%Y-%m-%d")
        state_file = cls.get_state_file_path(sym_kw)
        if os.path.exists(state_file):
            try:
                with open(state_file, "r", encoding="utf-8") as f:
                    state = json.load(f)
                    if isinstance(state, dict) and "current_state" in state:
                        if "symbol" not in state:
                            state["symbol"] = sym_kw
                        # If active_trade is already active, return state immediately
                        if state.get("current_state") in [cls.STATE_IN_TRADE, cls.STATE_ENTRY_PENDING] and state.get("active_trade"):
                            return state
                        # If IDLE, check if SignalTracker recorded a trade recommendation for today
                        sig = SignalTracker.get_signal(today_str, symbol=sym_kw)
                        if sig and sig.get("suggested_entry") and sig.get("full_contract"):
                            journal = TradeJournalManager.load_journal(symbol=sym_kw)
                            today_trades = [
                                t for t in journal 
                                if t.get("date") == today_str and (sym_kw in str(t.get("trading_symbol", "")).upper() or sym_kw in str(t.get("instrument", "")).upper())
                            ]
                            closed_trades = [t for t in today_trades if t.get("status") in ["HIT", "FAIL"] or t.get("is_closed") is True]
                            c_full = sig.get("full_contract", "")
                            is_closed = any(c_full in str(ct.get("instrument", "")) or sig.get("symbol", "") in str(ct.get("trading_symbol", "")) for ct in closed_trades)
                            if not is_closed:
                                spec_tr = get_asset_spec(symbol=sym_kw, contract=sig.get("symbol"))
                                s_entry = float(sig.get("suggested_entry", 0.0))
                                state["current_state"] = cls.STATE_IN_TRADE
                                state["symbol"] = sym_kw
                                state["active_trade"] = {
                                    "trade_num": len(closed_trades) + 1,
                                    "contract": sig.get("symbol", f"{sym_kw}_{sig.get('strike')}_{sig.get('contract_type')}"),
                                    "instrument": sig.get("full_contract", f"{sym_kw} {sig.get('strike')} {sig.get('contract_type')} ({sig.get('expiry')})"),
                                    "planned_entry": s_entry,
                                    "actual_entry": s_entry,
                                    "actual_entry_time": sig.get("trade_given_time", ""),
                                    "executed": "Signal Given",
                                    "sl": float(sig.get("suggested_sl", round(max(0.05, s_entry - spec_tr.sl_pts), 2))),
                                    "target": float(sig.get("suggested_exit", round(s_entry + spec_tr.target_pts, 2))),
                                    "direction": f"BUY {sig.get('contract_type', 'PE')}",
                                    "qty": spec_tr.lot_size * spec_tr.default_lots,
                                    "num_lots": spec_tr.default_lots,
                                    "lot_size": spec_tr.lot_size,
                                    "highest_price": s_entry,
                                    "trailing_sl": float(sig.get("suggested_sl", round(max(0.05, s_entry - spec_tr.sl_pts), 2))),
                                    "status": "Open",
                                    "confluence": float(sig.get("confluence_score", 75.0))
                                }
                                state["today_trade_count"] = len(closed_trades) + 1
                                cls.save_state(state, symbol=sym_kw)
                        return state
            except Exception as e:
                logger.debug(f"Error reading sequential state ({state_file}): {e}")

        # Initialize default state based on today's journal for this symbol
        today_str = datetime.now(IST).strftime("%Y-%m-%d")
        journal = TradeJournalManager.load_journal(symbol=sym_kw)
        today_trades = [
            t for t in journal 
            if t.get("date") == today_str and (sym_kw in str(t.get("trading_symbol", "")).upper() or sym_kw in str(t.get("instrument", "")).upper())
        ]

        open_trades = [t for t in today_trades if t.get("status") == "OPEN" or t.get("is_closed") is False]
        closed_trades = [t for t in today_trades if t.get("status") in ["HIT", "FAIL"] or t.get("is_closed") is True]

        if open_trades:
            active_tr = open_trades[-1]
            spec_tr = get_asset_spec(symbol=sym_kw, contract=active_tr.get("trading_symbol"))
            def_qty = spec_tr.lot_size
            init_state = {
                "current_state": cls.STATE_IN_TRADE,
                "symbol": spec_tr.symbol,
                "active_trade": {
                    "trade_num": len(closed_trades) + 1,
                    "contract": active_tr.get("trading_symbol", ""),
                    "instrument": active_tr.get("instrument", active_tr.get("trading_symbol", "")),
                    "planned_entry": float(active_tr.get("suggested_entry", active_tr.get("entry_price", 0.0))),
                    "actual_entry": float(active_tr.get("actual_entry_price", active_tr.get("entry_price", 0.0))),
                    "actual_entry_time": active_tr.get("actual_entry_time", ""),
                    "executed": "Yes",
                    "sl": float(active_tr.get("suggested_sl", max(0.05, active_tr.get("entry_price", 0.0) - spec_tr.sl_pts))),
                    "target": float(active_tr.get("suggested_exit", active_tr.get("entry_price", 0.0) + spec_tr.target_pts)),
                    "direction": active_tr.get("type", "BUY PE"),
                    "qty": int(active_tr.get("qty", def_qty)),
                    "num_lots": int(active_tr.get("num_lots", 1)),
                    "lot_size": int(active_tr.get("lot_size", def_qty)),
                    "highest_price": float(active_tr.get("actual_entry_price", active_tr.get("entry_price", 0.0))),
                    "trailing_sl": float(active_tr.get("suggested_sl", max(0.05, active_tr.get("entry_price", 0.0) - spec_tr.sl_pts))),
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
                "symbol": sym_kw,
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

        cls.save_state(init_state, symbol=symbol)
        return init_state

    @classmethod
    def save_state(cls, state: Dict[str, Any], symbol: Optional[str] = None):
        """Persists the engine state to disk for the appropriate symbol."""
        state["updated_at"] = datetime.now(IST).strftime("%Y-%m-%d %I:%M:%S %p IST")
        sym = symbol or state.get("symbol")
        if not sym and state.get("active_trade"):
            act = state["active_trade"]
            sym_str = str(act.get("contract", "")) + " " + str(act.get("instrument", ""))
            sym = resolve_symbol(sym_str)
        state_file = cls.get_state_file_path(sym)
        try:
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to persist sequential state to {state_file}: {e}")

    @classmethod
    def has_daily_loss_occurred_today(cls, symbol: Optional[str] = None) -> Tuple[bool, str]:
        """
        One-and-Done Institutional Circuit Breaker (with Solution 3 Re-Entry Exception):
        Returns (True, reason) if any trade executed today hit Stop-Loss or realized a negative PnL.
        EXCEPT: If a high-confidence setup was stopped out on an early wick and Re-Entry is armed!
        """
        sym_kw = resolve_symbol(symbol=symbol)
        
        # Solution 3: Check if Resumption Re-entry is currently armed for this symbol
        state = cls.get_state(symbol=sym_kw)
        re_arm = state.get("re_entry_armed")
        if re_arm and re_arm.get("armed"):
            exp_str = re_arm.get("expires_at", "")
            is_valid = True
            if exp_str:
                try:
                    exp_dt = datetime.strptime(exp_str.replace(" IST", ""), "%Y-%m-%d %I:%M:%S %p")
                    if datetime.now(IST).replace(tzinfo=None) > exp_dt:
                        is_valid = False
                        state["re_entry_armed"]["armed"] = False
                        cls.save_state(state, symbol=sym_kw)
                except Exception:
                    pass
            if is_valid:
                return False, f"RESUMPTION_RE_ENTRY_PERMITTED: Wick-sweep re-entry armed for {re_arm.get('instrument', sym_kw)}"

        today_str = datetime.now(IST).strftime("%Y-%m-%d")
        journal = TradeJournalManager.load_journal(symbol=sym_kw)
        today_losses = [
            t for t in journal
            if t.get("date") == today_str
            and (sym_kw in str(t.get("trading_symbol", "")).upper() or sym_kw in str(t.get("instrument", "")).upper())
            and (t.get("status") in ["FAIL", "SL Hit", "Hard Catastrophic SL Hit"] or float(t.get("realised_pnl", 0.0)) < 0)
        ]
        if today_losses:
            loss_t = today_losses[-1]
            return True, f"1 Stop-Loss Hit Today on {loss_t.get('trading_symbol', sym_kw)} ({loss_t.get('status')})"
        return False, ""

    @classmethod
    def check_theta_stagnation(
        cls,
        entry_time_str: str,
        current_ltp: float,
        entry_price: float,
        max_hold_minutes: int = 45,
        decay_tolerance_pts: float = 1.2
    ) -> Tuple[bool, int, float, str]:
        """
        Theta Stagnation Rule (Time-Stop Shield):
        If an intraday option position stays open for >= 45 minutes without reaching Target or SL,
        and premium has decayed by >= 1.2 pts due to sideways drift, triggers an early exit
        recommendation to stop theta bleed.
        Returns: (is_stagnant, elapsed_minutes, unrealized_pts, message)
        """
        try:
            clean_time = entry_time_str.replace(" IST", "").strip()
            today_date = datetime.now(IST).date()
            entry_dt = None
            for fmt in ("%I:%M:%S %p", "%H:%M:%S", "%I:%M %p"):
                try:
                    t_obj = datetime.strptime(clean_time, fmt).time()
                    entry_dt = datetime.combine(today_date, t_obj)
                    break
                except Exception:
                    continue
            if not entry_dt:
                return False, 0, 0.0, ""

            now_dt = datetime.now(IST).replace(tzinfo=None)
            elapsed_minutes = int((now_dt - entry_dt).total_seconds() / 60.0)
            if elapsed_minutes < 0:
                elapsed_minutes = 0

            unrealized_pts = round(current_ltp - entry_price, 2)
            if elapsed_minutes >= max_hold_minutes and unrealized_pts <= -decay_tolerance_pts:
                msg = f"Trade open for {elapsed_minutes} mins without momentum. Premium decayed {unrealized_pts:+.2f} pts due to theta. Early exit recommended."
                return True, elapsed_minutes, unrealized_pts, msg
            return False, elapsed_minutes, unrealized_pts, ""
        except Exception:
            return False, 0, 0.0, ""

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
        qty: int = 0,
        num_lots: int = 1,
        symbol: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Immediately transitions engine to IN-TRADE (ACTIVE MONITORING).
        Zero delay: called instantly as soon as a buy entry trigger is validated.
        Completely prevents flapping back to ARMED state when price fluctuates.
        """
        spec = get_asset_spec(symbol=symbol, contract=f"{contract} {instrument}")
        active_sym = spec.symbol
        if qty <= 0:
            qty = spec.lot_size * max(1, num_lots)
        state = cls.get_state(symbol=active_sym)
        curr_state = state.get("current_state", cls.STATE_IDLE)

        # One-and-Done Daily Circuit Breaker Guard
        has_loss, loss_reason = cls.has_daily_loss_occurred_today(symbol=active_sym)
        if has_loss:
            return {
                "success": False,
                "msg": f"⛔ CIRCUIT BREAKER ACTIVE ({active_sym}): {loss_reason}. All new entries locked for today to preserve capital.",
                "state": state
            }

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

        hard_sl_pts = round((actual_p - sl_p) * 1.5, 2)
        hard_sl = round(max(0.05, actual_p - hard_sl_pts), 2)
        is_reentry = bool(state.get("re_entry_armed", {}).get("armed"))

        active_trade = {
            "trade_num": next_trade_num,
            "contract": contract,
            "instrument": instrument,
            "planned_entry": actual_p,
            "actual_entry": actual_p,
            "actual_entry_time": now_time_str,
            "executed": "Yes",
            "sl": sl_p,
            "soft_sl": sl_p,
            "hard_sl": hard_sl,
            "wick_touches": 0,
            "is_re_entry": is_reentry,
            "target": target_p,
            "target_2": round(actual_p + getattr(get_asset_spec(contract=contract, symbol=active_sym), "target_2_pts", 15.0), 2),
            "direction": direction,
            "expiry": expiry,
            "qty": int(qty),
            "num_lots": int(num_lots),
            "t1_qty": int(qty) // 2,
            "t2_qty": int(qty) - (int(qty) // 2),
            "t1_status": "PENDING",
            "t2_status": "PENDING",
            "confluence": round(float(confluence), 1),
            "highest_price": actual_p,
            "trailing_sl": sl_p,
            "status": "Open (Re-Entry)" if is_reentry else "Open",
            "proposed_at": now_time_str,
            "symbol": active_sym
        }

        state["current_state"] = cls.STATE_IN_TRADE
        state["symbol"] = active_sym
        state["active_trade"] = active_trade
        if is_reentry:
            state["re_entry_armed"] = None
        cls.save_state(state, symbol=active_sym)

        today_str = datetime.now(IST).strftime("%Y-%m-%d")
        spec_c = get_asset_spec(contract=contract, symbol=active_sym)
        try:
            SignalTracker.save_signal({
                "date": today_str,
                "trade_given_time": now_time_str,
                "full_contract": instrument,
                "symbol": contract,
                "contract_type": "PE" if "PE" in contract else "CE",
                "strike": int("".join(filter(str.isdigit, contract)) or spec_c.default_strike),
                "expiry": expiry,
                "suggested_entry": actual_p,
                "suggested_exit": target_p,
                "suggested_sl": sl_p,
                "confluence_score": confluence
            })
        except Exception as e:
            logger.debug(f"SignalTracker save error: {e}")

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
        qty: int = 0,
        num_lots: int = 1,
        symbol: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Rule 1: Propose a new trade setup. Strictly forbidden if an active or pending trade exists.
        Transitions state to ENTRY PENDING.
        """
        spec = get_asset_spec(symbol=symbol, contract=f"{contract} {instrument}")
        active_sym = spec.symbol
        if qty <= 0:
            qty = spec.lot_size * max(1, num_lots)
        state = cls.get_state(symbol=active_sym)
        curr_state = state.get("current_state", cls.STATE_IDLE)

        # One-and-Done Daily Circuit Breaker Guard
        has_loss, loss_reason = cls.has_daily_loss_occurred_today(symbol=active_sym)
        if has_loss:
            return {
                "success": False,
                "msg": f"⛔ CIRCUIT BREAKER ACTIVE ({active_sym}): {loss_reason}. All new entries locked for today to preserve capital.",
                "state": state
            }

        # Zero Parallel Signals Guard
        if curr_state in [cls.STATE_ENTRY_PENDING, cls.STATE_IN_TRADE]:
            return {
                "success": False,
                "msg": f"⛔ REJECTED: Sequential Rule #1 active. Current state is '{curr_state}'. Zero parallel trades permitted.",
                "state": state
            }

        # Robust regex strike parsing: extract 4-5 digit strike preceding CE/PE
        import re
        m = re.search(r'(\d{4,5})\s*(?:CE|PE)', contract)
        if m:
            parsed_strike = int(m.group(1))
        else:
            digits = re.findall(r'\d{3,5}', contract)
            spec_fallback = get_asset_spec(symbol=active_sym)
            parsed_strike = int(digits[-1]) if digits else spec_fallback.default_strike

        limit_entry = round(float(planned_entry) + float(spec.limit_collar_pts), 2)
        sl_val = round(float(sl), 2)
        hard_sl_pts = round((float(planned_entry) - sl_val) * 1.5, 2)
        hard_sl = round(max(0.05, float(planned_entry) - hard_sl_pts), 2)
        is_reentry = bool(state.get("re_entry_armed", {}).get("armed"))

        next_trade_num = int(state.get("today_trade_count", 0)) + 1
        active_trade = {
            "trade_num": next_trade_num,
            "contract": contract,
            "instrument": instrument,
            "planned_entry": round(float(planned_entry), 2),
            "limit_entry": limit_entry,
            "actual_entry": None,
            "actual_entry_time": None,
            "executed": "Pending",
            "sl": sl_val,
            "soft_sl": sl_val,
            "hard_sl": hard_sl,
            "wick_touches": 0,
            "is_re_entry": is_reentry,
            "target": round(float(target), 2),
            "target_2": round(float(planned_entry) + getattr(spec, "target_2_pts", spec.target_pts * 2.0), 2),
            "direction": direction,
            "expiry": expiry,
            "qty": int(qty),
            "num_lots": int(num_lots),
            "t1_qty": int(qty) // 2,
            "t2_qty": int(qty) - (int(qty) // 2),
            "t1_status": "PENDING",
            "t2_status": "PENDING",
            "confluence": round(float(confluence), 1),
            "highest_price": round(float(planned_entry), 2),
            "trailing_sl": sl_val,
            "status": "Entry Pending (Re-Entry)" if is_reentry else "Entry Pending",
            "proposed_at": datetime.now(IST).strftime("%I:%M:%S %p IST"),
            "symbol": active_sym
        }

        state["current_state"] = cls.STATE_ENTRY_PENDING
        state["symbol"] = active_sym
        state["active_trade"] = active_trade
        cls.save_state(state, symbol=active_sym)

        # Also register in SignalTracker and EmpiricalCalibrationEngine
        try:
            SignalTracker.save_signal({
                "date": datetime.now(IST).strftime("%Y-%m-%d"),
                "trade_given_time": active_trade["proposed_at"],
                "full_contract": instrument,
                "symbol": contract,
                "contract_type": "PE" if "PE" in contract else "CE",
                "strike": parsed_strike,
                "expiry": expiry,
                "suggested_entry": planned_entry,
                "limit_entry": limit_entry,
                "suggested_exit": target,
                "suggested_sl": sl,
                "confluence_score": confluence
            })
        except Exception:
            pass

        try:
            from empirical_calibration_engine import EmpiricalCalibrationEngine
            EmpiricalCalibrationEngine.record_signal_snapshot(
                signal_id=f"TRD-{datetime.now(IST).strftime('%Y%m%d')}-{next_trade_num:02d}-{contract}",
                engine_eval={"dominant_score": confluence, "win_expectancy_pct": 58.0},
                instrument=instrument,
                direction=direction,
                planned_entry=planned_entry,
                target=target,
                sl=sl
            )
        except Exception:
            pass

        return {
            "success": True,
            "msg": f"✅ Trade #{next_trade_num} proposed: {instrument} @ ₹{planned_entry:.2f} (SL-LMT Cap: ₹{limit_entry:.2f}). Waiting for Groww fill confirmation.",
            "state": state
        }

    @classmethod
    def confirm_groww_fill(
        cls,
        confirmed: bool,
        actual_price: Optional[float] = None,
        actual_time: Optional[str] = None,
        notes: str = "",
        symbol: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Rule 2: Verification with Groww.
        - If confirmed (Yes): transitions to IN-TRADE (ACTIVE MONITORING) with actual entry price & time.
        - If rejected / cancelled (No): transitions back to IDLE / SCANNING.
        """
        state = cls.get_state(symbol=symbol)
        if state.get("current_state") != cls.STATE_ENTRY_PENDING:
            return {
                "success": False,
                "msg": f"Engine not in ENTRY PENDING state (current: {state.get('current_state')}).",
                "state": state
            }

        active = state.get("active_trade")
        if not active:
            state["current_state"] = cls.STATE_IDLE
            cls.save_state(state, symbol=symbol)
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
            cls.save_state(state, symbol=symbol)
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
            cls.save_state(state, symbol=symbol)
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
        starting_cash: Optional[float] = None,
        symbol: Optional[str] = None,
        is_candle_closed: bool = True
    ) -> Dict[str, Any]:
        """
        Rule 3: Monitor Active Trade with Two-Tier SL & Chandelier Trailing.
        Checks Target Hit, Hard Catastrophic SL, Soft Candle Close SL, and Chandelier Trailing.
        """
        state = cls.get_state(symbol=symbol)
        if state.get("current_state") != cls.STATE_IN_TRADE:
            return {"active": False, "state": state}

        active = state.get("active_trade")
        if not active:
            state["current_state"] = cls.STATE_IDLE
            cls.save_state(state, symbol=symbol)
            return {"active": False, "state": state}

        current_ltp = float(current_ltp)
        actual_entry = float(active.get("actual_entry", active.get("planned_entry", 0.0)))
        target = float(active.get("target", actual_entry + 10.0))
        sl = float(active.get("sl", max(0.05, actual_entry - 4.5)))
        contract = active.get("contract", "")
        spec_act = get_asset_spec(symbol=symbol or state.get("symbol"), contract=contract)
        active_sym = spec_act.symbol
        qty = int(active.get("qty", spec_act.lot_size))

        # Synchronize active trade parameters with authentic Groww broker positions & orders
        if groww_feed and getattr(groww_feed, "is_connected", False):
            try:
                open_pos_list = []
                if hasattr(groww_feed, "get_live_positions"):
                    pos_resp = groww_feed.get_live_positions()
                    if isinstance(pos_resp, dict):
                        open_pos_list = pos_resp.get("open_positions") or pos_resp.get("positions") or []
                    elif isinstance(pos_resp, list):
                        open_pos_list = pos_resp

                executed_today = groww_feed.get_executed_trades_today(symbol_filter=active_sym)

                import re
                m_strk = re.search(r"(\d{4,6})", contract + " " + str(active.get("instrument", "")))
                strike_str = m_strk.group(1) if m_strk else ""
                opt_type = "PE" if ("PE" in contract.upper() or "PUT" in str(active.get("instrument", "")).upper() or "PE" in str(active.get("direction", "")).upper()) else "CE"

                matching_pos = None
                for p in open_pos_list:
                    p_sym = str(p.get("trading_symbol", "")).upper()
                    if active_sym in p_sym and (strike_str in p_sym if strike_str else True) and (opt_type in p_sym if opt_type else True):
                        matching_pos = p
                        break

                matching_trade = None
                for ex_tr in executed_today:
                    ex_sym = str(ex_tr.get("symbol", "")).upper()
                    if active_sym in ex_sym and (strike_str in ex_sym if strike_str else True) and (opt_type in ex_sym if opt_type else True):
                        matching_trade = ex_tr
                        break

                if matching_pos:
                    p_qty = int(matching_pos.get("quantity", 0))
                    p_entry = float(matching_pos.get("net_price", 0.0) or matching_pos.get("credit_price", 0.0) or (matching_trade.get("entry_price", 0.0) if matching_trade else 0.0))
                    p_time = matching_trade.get("entry_time", "") if matching_trade else ""

                    changed = False
                    if p_qty > 0 and p_qty != active.get("qty"):
                        active["qty"] = p_qty
                        qty = p_qty
                        lot_sz = max(1, getattr(spec_act, "lot_size", 65 if active_sym == "NIFTY" else 15))
                        active["num_lots"] = max(1, round(p_qty / lot_sz))
                        changed = True
                    if p_entry > 0 and abs(active.get("actual_entry", 0.0) - p_entry) > 0.01:
                        active["actual_entry"] = round(p_entry, 2)
                        active["planned_entry"] = round(p_entry, 2)
                        actual_entry = round(p_entry, 2)
                        spec_sl = float(getattr(spec_act, 'sl_pts', 36.0 if active_sym == 'NIFTY' else 4.5))
                        spec_tgt = float(getattr(spec_act, 'target_pts', 50.0 if active_sym == 'NIFTY' else 10.0))
                        active["sl"] = round(max(0.05, actual_entry - spec_sl), 2)
                        active["target"] = round(actual_entry + spec_tgt, 2)
                        target = active["target"]
                        sl = active["sl"]
                        if not active.get("breakeven_activated"):
                            active["trailing_sl"] = active["sl"]
                        changed = True
                    if p_time and ("T" in p_time or "-" in p_time):
                        try:
                            t_part = p_time.split("T")[1].split(".")[0]
                            dt = datetime.strptime(t_part, "%H:%M:%S")
                            active["actual_entry_time"] = dt.strftime("%I:%M:%S %p IST")
                            changed = True
                        except Exception:
                            pass
                    if matching_pos.get("trading_symbol") and matching_pos.get("trading_symbol") != active.get("contract"):
                        active["contract"] = matching_pos.get("trading_symbol")
                        contract = active["contract"]
                        changed = True
                    if changed:
                        active["executed"] = "Groww Verified"
                        cls.save_state(state, symbol=symbol)

                # Check if Groww recorded a closed position exit
                if matching_trade and matching_trade.get("is_closed", False):
                    journal_entries = TradeJournalManager.load_journal(starting_cash=starting_cash, symbol=active_sym)
                    used_exit_times = {str(j.get("actual_exit_time")) for j in journal_entries if j.get("actual_exit_time")}
                    raw_ex_t = str(matching_trade.get("exit_time", ""))
                    if not (raw_ex_t and any(raw_ex_t in str(x) or str(x) in raw_ex_t for x in used_exit_times if x)):
                        exit_p = float(matching_trade.get("exit_price", current_ltp))
                        exit_t = matching_trade.get("exit_time", datetime.now(IST).strftime("%I:%M:%S %p IST"))
                        real_pnl = float(matching_trade.get("realised_pnl", (exit_p - actual_entry) * qty))
                        effective_sl_calc = max(sl, active.get("trailing_sl", sl))
                        if exit_p >= (target - 0.25):
                            status = "Target Hit"
                        elif exit_p <= (effective_sl_calc + 0.25):
                            status = "SL Hit"
                        elif real_pnl > 0:
                            status = "Discretionary Exit (+Profit)"
                        else:
                            status = "Discretionary Exit (-Loss)"
                        return cls.close_trade(
                            exit_price=exit_p,
                            status=status,
                            exit_time=exit_t,
                            notes=f"Auto-synced Groww Position Exit @ ₹{exit_p:.2f} ({status})",
                            starting_cash=starting_cash,
                            symbol=active_sym
                        )
            except Exception as e:
                logger.debug(f"Error checking broker sync for active trade: {e}")

        # Resolve real-time live LTP from Groww broker feed if connected (absolute zero latency)
        if groww_feed and getattr(groww_feed, "is_connected", False) and hasattr(groww_feed, "get_option_contract_ltp"):
            try:
                gw_ltp = groww_feed.get_option_contract_ltp(contract, symbol=active_sym)
                if not gw_ltp or gw_ltp <= 0:
                    gw_ltp = groww_feed.get_option_contract_ltp(active.get("instrument", ""), symbol=active_sym)
                if gw_ltp and gw_ltp > 0:
                    current_ltp = float(gw_ltp)
            except Exception:
                pass

        # Update high-water mark & Tiered Breakeven Escalator
        if current_ltp > active.get("highest_price", actual_entry):
            active["highest_price"] = round(current_ltp, 2)
        
        profit_pts = round(current_ltp - actual_entry, 2)
        peak_profit_pts = round(float(active.get("highest_price", actual_entry)) - actual_entry, 2)

        # Milestone 1: At Breakeven threshold -> Move SL to Cost
        be_thresh = float(getattr(spec_act, 'be_pts', 3.5))
        lock_thresh = float(getattr(spec_act, 'profit_lock_trigger', 5.0))
        lock_val = float(getattr(spec_act, 'profit_lock_locked', 2.5))

        if peak_profit_pts >= be_thresh:
            be_sl = round(actual_entry + 0.10, 2)
            if be_sl > active.get("trailing_sl", sl):
                active["trailing_sl"] = be_sl
                active["breakeven_activated"] = True

        # Milestone 2: At Profit Lock threshold -> Lock Profit
        if peak_profit_pts >= lock_thresh:
            lock_sl = round(actual_entry + lock_val, 2)
            if lock_sl > active.get("trailing_sl", sl):
                active["trailing_sl"] = lock_sl
                active["profit_lock_activated"] = True

        # Solution 4: Chandelier / Trailing ATR Exit once trade achieves 1:1 Risk-Reward
        initial_risk_pts = round(actual_entry - sl, 2) if actual_entry > sl else float(spec_act.sl_pts)
        if profit_pts >= initial_risk_pts:
            if not active.get("breakeven_activated"):
                active["trailing_sl"] = round(actual_entry + 0.10, 2)
                active["breakeven_activated"] = True
            
            # Dynamic Chandelier Trailing behind high water mark
            ch_mult = float(getattr(spec_act, 'chandelier_mult', 2.0))
            atr_est = max(1.0, float(getattr(spec_act, 'sl_pts', 10.0)) / max(0.5, float(getattr(spec_act, 'atr_multiplier_sl', 1.5))))
            ch_atr_dist = round(ch_mult * atr_est, 2)
            high_water = float(active.get("highest_price", actual_entry))
            ch_trail_sl = round(max(actual_entry, high_water - ch_atr_dist), 2)
            if ch_trail_sl > active.get("trailing_sl", actual_entry):
                active["trailing_sl"] = ch_trail_sl
                active["trailing_mode"] = "CHANDELIER_ATR"

        effective_sl = max(sl, active.get("trailing_sl", sl))
        hard_sl = float(active.get("hard_sl", max(0.05, actual_entry - (float(spec_act.sl_pts) * 1.5))))
        unrealized_pnl = round((current_ltp - actual_entry) * qty, 2)
        active["current_ltp"] = current_ltp
        active["unrealized_pnl"] = unrealized_pnl

        # Option 1 Multi-Tranche Execution (50% Bank at T1 + 50% Runner)
        target_1 = target
        target_2 = float(active.get("target_2", actual_entry + getattr(spec_act, 'target_2_pts', spec_act.target_pts * 2.0)))
        t1_status = active.get("t1_status", "PENDING")
        t1_qty = int(active.get("t1_qty", qty // 2))
        t2_qty = qty - t1_qty

        # Scenario 1: Tranche 1 is still pending
        if t1_status == "PENDING":
            if current_ltp >= target_1:
                # Bank Tranche 1 (50% Qty)
                active["t1_status"] = "BANKED"
                active["t1_exit_price"] = current_ltp
                active["t1_exit_time"] = datetime.now(IST).strftime("%I:%M:%S %p IST")
                t1_pts = round(current_ltp - actual_entry, 2)
                active["t1_pnl"] = round(t1_pts * t1_qty, 2)
                # Lock Stop-Loss for Tranche 2 Runner at Cost (Breakeven Free Roll)
                active["trailing_sl"] = actual_entry
                active["breakeven_activated"] = True
                active["t2_status"] = "RUNNER_ACTIVE"
                active["status"] = "T1 Banked - Runner Active"
                active["target_2"] = target_2
                active["notes"] = f"Tranche 1 (50%) Banked @ ₹{current_ltp:.2f} (+{t1_pts} pts). Runner Stop-Loss locked at Cost (₹{actual_entry:.2f}) trailing to Target 2 (₹{target_2:.2f})"
                cls.save_state(state, symbol=active_sym)
                return {
                    "active": True,
                    "tranche_event": "T1_BANKED",
                    "t1_pnl": active["t1_pnl"],
                    "current_ltp": current_ltp,
                    "state": state
                }
            # Solution 2: Two-Tier Stop Loss Check
            # Tier 1: Emergency Hard Catastrophic Stop Loss (Instant Broker Tick Execution)
            elif current_ltp <= hard_sl:
                return cls.close_trade(
                    exit_price=current_ltp,
                    status="Hard Catastrophic SL Hit",
                    notes=f"Emergency Hard SL Hit: ₹{current_ltp:.2f} <= ₹{hard_sl:.2f} (-{round(actual_entry - current_ltp, 2)} pts)",
                    starting_cash=starting_cash,
                    symbol=active_sym
                )
            # Tier 2: Technical Soft Stop Loss (Filtered against intra-candle wick sweeps)
            elif current_ltp <= effective_sl:
                if not is_candle_closed:
                    active["wick_touches"] = int(active.get("wick_touches", 0)) + 1
                    active["wick_guard_alert"] = f"Wick touch @ ₹{current_ltp:.2f} <= ₹{effective_sl:.2f}. Soft SL active, waiting for 5m candle close confirmation."
                    cls.save_state(state, symbol=active_sym)
                    return {
                        "active": True,
                        "wick_sweep_prevented": True,
                        "current_ltp": current_ltp,
                        "state": state
                    }
                else:
                    return cls.close_trade(
                        exit_price=current_ltp,
                        status="SL Hit",
                        notes=f"5m Candle Close Soft SL Triggered: ₹{current_ltp:.2f} <= ₹{effective_sl:.2f} (-{round(actual_entry - current_ltp, 2)} pts)",
                        starting_cash=starting_cash,
                        symbol=active_sym
                    )

        # Scenario 2: Tranche 1 already banked! Monitoring Tranche 2 Runner
        elif t1_status == "BANKED":
            if current_ltp >= target_2:
                # Target 2 hit!
                t2_pts = round(current_ltp - actual_entry, 2)
                active["t2_status"] = "T2_HIT"
                active["t2_exit_price"] = current_ltp
                active["t2_exit_time"] = datetime.now(IST).strftime("%I:%M:%S %p IST")
                active["t2_pnl"] = round(t2_pts * t2_qty, 2)
                t1_pts_gained = round(float(active.get("t1_exit_price", target_1)) - actual_entry, 2)
                return cls.close_trade(
                    exit_price=current_ltp,
                    status=f"T1 (+{t1_pts_gained}) | T2 HIT (+{t2_pts})",
                    notes=f"Option 1 Runner: T1 Banked (+{t1_pts_gained} pts) + T2 Runner Hit (+{t2_pts} pts)",
                    starting_cash=starting_cash,
                    symbol=active_sym
                )
            elif current_ltp <= active.get("trailing_sl", actual_entry):
                # Runner trails out at Cost (Breakeven)
                exit_cost_p = active.get("trailing_sl", actual_entry)
                active["t2_status"] = "COST_EXIT"
                active["t2_exit_price"] = exit_cost_p
                active["t2_exit_time"] = datetime.now(IST).strftime("%I:%M:%S %p IST")
                active["t2_pnl"] = 0.0
                t1_pts_gained = round(float(active.get("t1_exit_price", target_1)) - actual_entry, 2)
                return cls.close_trade(
                    exit_price=exit_cost_p,
                    status=f"T1 (+{t1_pts_gained}) | TRAIL COST (0.0)",
                    notes=f"Option 1 Runner: T1 Banked (+{t1_pts_gained} pts) + Runner Protected @ Cost (₹{actual_entry:.2f})",
                    starting_cash=starting_cash,
                    symbol=active_sym
                )

        # Still in trade
        cls.save_state(state, symbol=active_sym)
        return {
            "active": True,
            "current_ltp": current_ltp,
            "unrealized_pnl": unrealized_pnl,
            "distance_to_target": round(target - current_ltp, 2),
            "distance_to_sl": round(current_ltp - effective_sl, 2),
            "state": state
        }

    @classmethod
    def sync_with_groww_positions(
        cls,
        groww_feed: Any = None,
        symbol: Optional[str] = None,
        starting_cash: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Manually or programmatically triggers a 100% full reconciliation against Groww live positions and orders.
        Updates active_trade entry price, quantity, lots, stop loss, target, and unrealized P&L.
        """
        if not groww_feed:
            try:
                from groww_market_feed import GrowwMarketFeed
                groww_feed = GrowwMarketFeed.get_instance()
            except Exception:
                pass

        if not groww_feed or not getattr(groww_feed, "is_connected", False):
            return {"status": "ERROR", "message": "Groww feed not connected"}

        sym_kw = resolve_symbol(symbol=symbol)
        spec = get_asset_spec(sym_kw)

        # Force refresh positions and executed trades from Groww API
        pos_data = groww_feed.get_live_positions(force_refresh=True)
        open_positions = pos_data.get("open_positions", []) if isinstance(pos_data, dict) else []
        if not open_positions and isinstance(pos_data, dict):
            open_positions = [p for p in pos_data.get("positions", []) if int(p.get("quantity", 0)) != 0]

        executed_today = groww_feed.get_executed_trades_today(symbol_filter=sym_kw, force_refresh=True)

        state = cls.get_state(symbol=sym_kw)
        active = state.get("active_trade")

        # Find matching Groww position
        matching_pos = None
        for p in open_positions:
            p_sym = str(p.get("trading_symbol", "")).upper()
            if sym_kw in p_sym:
                matching_pos = p
                break

        matching_trade = None
        for t in executed_today:
            t_sym = str(t.get("symbol", "")).upper()
            if sym_kw in t_sym:
                matching_trade = t
                break

        if matching_pos:
            qty = int(matching_pos.get("quantity", 0))
            entry_p = float(matching_pos.get("net_price", 0.0) or matching_pos.get("credit_price", 0.0))
            if entry_p <= 0 and matching_trade:
                entry_p = float(matching_trade.get("entry_price", 0.0))
            
            entry_time = ""
            if matching_trade and matching_trade.get("entry_time"):
                raw_t = matching_trade.get("entry_time")
                try:
                    if "T" in raw_t:
                        t_part = raw_t.split("T")[1].split(".")[0]
                        dt = datetime.strptime(t_part, "%H:%M:%S")
                        entry_time = dt.strftime("%I:%M:%S %p IST")
                    else:
                        entry_time = str(raw_t)
                except Exception:
                    entry_time = str(raw_t)

            trading_sym = str(matching_pos.get("trading_symbol", ""))

            # Resolve live LTP for this contract
            live_ltp = groww_feed.get_option_contract_ltp(trading_sym, symbol=sym_kw)
            if not live_ltp or live_ltp <= 0:
                live_ltp = entry_p

            if not active:
                active = {
                    "trade_num": state.get("today_trade_count", 0) + 1,
                    "contract": trading_sym,
                    "instrument": f"{sym_kw} Contract ({trading_sym})",
                    "planned_entry": entry_p,
                    "actual_entry": entry_p,
                    "actual_entry_time": entry_time or datetime.now(IST).strftime("%I:%M:%S %p IST"),
                    "executed": "Groww Verified",
                    "sl": round(max(0.05, entry_p - float(getattr(spec, 'sl_pts', 36.0))), 2),
                    "target": round(entry_p + float(getattr(spec, 'target_pts', 50.0)), 2),
                    "direction": "BUY PE" if "PE" in trading_sym else "BUY CE",
                    "qty": qty,
                    "num_lots": max(1, round(qty / max(1, getattr(spec, 'lot_size', 65)))),
                    "lot_size": getattr(spec, 'lot_size', 65),
                    "highest_price": max(entry_p, live_ltp),
                    "trailing_sl": round(max(0.05, entry_p - float(getattr(spec, 'sl_pts', 36.0))), 2),
                    "status": "Open",
                    "current_ltp": live_ltp,
                    "unrealized_pnl": round((live_ltp - entry_p) * qty, 2)
                }
                state["current_state"] = cls.STATE_IN_TRADE
                state["active_trade"] = active
            else:
                active["contract"] = trading_sym
                active["actual_entry"] = entry_p
                active["planned_entry"] = entry_p
                active["qty"] = qty
                active["num_lots"] = max(1, round(qty / max(1, getattr(spec, 'lot_size', 65))))
                if entry_time:
                    active["actual_entry_time"] = entry_time
                active["sl"] = round(max(0.05, entry_p - float(getattr(spec, 'sl_pts', 36.0))), 2)
                active["target"] = round(entry_p + float(getattr(spec, 'target_pts', 50.0)), 2)
                if not active.get("breakeven_activated"):
                    active["trailing_sl"] = active["sl"]
                active["current_ltp"] = live_ltp
                active["unrealized_pnl"] = round((live_ltp - entry_p) * qty, 2)
                active["executed"] = "Groww Verified"

            cls.save_state(state, symbol=sym_kw)

            # Update shadow signals log
            try:
                from trade_journal_manager import ShadowSignalTracker
                recs = ShadowSignalTracker.load_records(symbol=sym_kw)
                for r in recs:
                    if r.get("date") == datetime.now(IST).strftime("%Y-%m-%d") and sym_kw in str(r.get("symbol", "")):
                        r["actual_entry_price"] = entry_p
                        r["entry"] = entry_p
                        r["target"] = active["target"]
                        r["sl"] = active["sl"]
                        r["current_price"] = live_ltp
                        if entry_time:
                            r["actual_entry_time"] = entry_time
                ShadowSignalTracker.save_records(recs)
            except Exception as e:
                logger.debug(f"Shadow tracker sync update error: {e}")

            return {"status": "SUCCESS", "active_trade": active}

        return {"status": "NO_POSITION", "message": f"No open positions found in Groww for {sym_kw}"}

    @classmethod
    def close_trade(
        cls,
        exit_price: float,
        status: str,
        exit_time: Optional[str] = None,
        notes: str = "",
        starting_cash: Optional[float] = None,
        symbol: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Rule 4: Close and Audit Active Trade.
        Records outcome in daily journal and transitions engine to TRADE CLOSED & AUDITED.
        """
        state = cls.get_state(symbol=symbol)
        active = state.get("active_trade")
        if not active:
            state["current_state"] = cls.STATE_IDLE
            cls.save_state(state, symbol=symbol)
            return {"success": False, "msg": "No active trade to close.", "state": state}

        exit_p = round(float(exit_price), 2)
        exit_t = exit_time or datetime.now(IST).strftime("%I:%M:%S %p IST")
        actual_entry = float(active.get("actual_entry", active.get("planned_entry", 0.0)))
        t_num = active.get("trade_num", int(state.get("today_trade_count", 0)) + 1)
        inst = active.get("instrument", "")
        sym = active.get("contract", "")
        spec_close = get_asset_spec(symbol=symbol or state.get("symbol"), contract=sym)
        active_sym = spec_close.symbol
        def_lot_sz = spec_close.lot_size
        qty = int(active.get("qty", def_lot_sz))
        if active.get("t1_status") == "BANKED":
            t1_pnl = float(active.get("t1_pnl", 0.0))
            t2_qty = int(active.get("t2_qty", qty - (qty // 2)))
            t2_pts = round(exit_p - actual_entry, 2)
            t2_pnl = round(t2_pts * t2_qty, 2)
            pnl = round(t1_pnl + t2_pnl, 2)
            pts = round(pnl / qty, 2) if qty > 0 else t2_pts
        else:
            pts = round(exit_p - actual_entry, 2)
            pnl = round(pts * qty, 2)
        today_str = datetime.now(IST).strftime("%Y-%m-%d")

        # Record in daily journal ledger
        journal_rec = {
            "id": f"TRD-{today_str.replace('-', '')}-{t_num:02d}-{sym}",
            "date": today_str,
            "day": datetime.now(IST).strftime("%A"),
            "symbol": active_sym,
            "trading_symbol": sym,
            "instrument": inst,
            "type": active.get("direction", "BUY PE"),
            "decision": "TRADABLE (A+ SETUP)",
            "source": "GROWW_VERIFIED",
            "is_closed": True,
            "trade_given_time": active.get("proposed_at", "09:15:00 AM IST"),
            "suggested_contract": inst,
            "suggested_entry": active.get("planned_entry", actual_entry),
            "suggested_exit": active.get("target", actual_entry + spec_close.target_pts),
            "suggested_sl": active.get("sl", max(0.05, actual_entry - spec_close.sl_pts)),
            "suggested_target_pts": round(active.get("target", actual_entry + spec_close.target_pts) - active.get("planned_entry", actual_entry), 2),
            "suggested_sl_pts": round(active.get("planned_entry", actual_entry) - active.get("sl", max(0.05, actual_entry - spec_close.sl_pts)), 2),
            "actual_entry_time": active.get("actual_entry_time", exit_t),
            "actual_entry_price": actual_entry,
            "entry_price": actual_entry,
            "actual_exit_time": exit_t,
            "actual_exit_price": exit_p,
            "exit_price": exit_p,
            "num_lots": active.get("num_lots", 1),
            "lot_size": active.get("lot_size", def_lot_sz),
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
        # Only record into authentic daily trade ledger if genuinely executed on Groww!
        if active.get("executed") == "Yes" and active.get("actual_entry"):
            TradeJournalManager.add_or_update_entry(journal_rec, starting_cash=starting_cash)

        # Label outcome in empirical calibration dataset
        try:
            from empirical_calibration_engine import EmpiricalCalibrationEngine
            EmpiricalCalibrationEngine.resolve_trade_outcome(
                signal_id=journal_rec["id"],
                target_hit=(pnl > 0 or status == "Target Hit"),
                realized_pnl=pnl,
                realized_pts=pts,
                exit_reason=status
            )
        except Exception:
            pass

        # Transition state
        closed_summary = {
            "trade_num": t_num,
            "instrument": inst,
            "planned_entry": active.get("planned_entry", actual_entry),
            "actual_entry": actual_entry,
            "executed": "Yes",
            "sl": active.get("sl", max(0.05, actual_entry - spec_close.sl_pts)),
            "target": active.get("target", actual_entry + spec_close.target_pts),
            "status": status,
            "exit_price": exit_p,
            "exit_time": exit_t,
            "pnl": f"{'+' if pnl >= 0 else ''}₹{pnl:,.2f} ({'+' if pts >= 0 else ''}{pts:.2f} pts)"
        }

        state["current_state"] = cls.STATE_TRADE_CLOSED
        state["symbol"] = active_sym
        state["active_trade"] = None
        state["last_closed_trade"] = closed_summary
        state["today_trade_count"] = max(int(state.get("today_trade_count", 0)), t_num)

        # Solution 3: Resumption Re-Entry Arming Protocol (Single-Shot Second Chance Guard)
        if active.get("is_re_entry") or int(state.get("today_trade_count", 0)) >= 2:
            # SAFEGUARD: Never arm re-entry if trade was already a re-entry, or if max 2 trades hit today
            state["re_entry_armed"] = None
        elif "SL" in status and float(active.get("confluence", 70.0)) >= getattr(spec_close, "re_entry_min_confidence", 65.0):
            t_open_mins = 5
            try:
                clean_t = str(active.get("actual_entry_time", "")).replace(" IST", "").strip()
                for fmt in ("%I:%M:%S %p", "%H:%M:%S"):
                    try:
                        t_obj = datetime.strptime(clean_t, fmt).time()
                        t_open_mins = int((datetime.now(IST).replace(tzinfo=None) - datetime.combine(datetime.now(IST).date(), t_obj)).total_seconds() / 60.0)
                        break
                    except Exception:
                        continue
            except Exception:
                pass

            if t_open_mins <= 15:
                state["re_entry_armed"] = {
                    "armed": True,
                    "symbol": active_sym,
                    "contract": sym,
                    "instrument": inst,
                    "direction": active.get("direction", "BUY PE"),
                    "confluence": float(active.get("confluence", 70.0)),
                    "planned_entry": float(active.get("planned_entry", actual_entry)),
                    "actual_entry": actual_entry,
                    "wick_extreme_sl": exit_p,
                    "stop_loss_pts": round(abs(actual_entry - exit_p), 2),
                    "target": float(active.get("target", 0.0)),
                    "target_2": float(active.get("target_2", 0.0)),
                    "qty": qty,
                    "num_lots": int(active.get("num_lots", 1)),
                    "armed_at": datetime.now(IST).strftime("%Y-%m-%d %I:%M:%S %p IST"),
                    "expires_at": (datetime.now(IST) + timedelta(minutes=15)).strftime("%Y-%m-%d %I:%M:%S %p IST"),
                    "notes": f"High conviction ({active.get('confluence')}%) setup stopped on early wick at {exit_t}. Re-entry armed for 15 mins if price breaks back past entry level ₹{actual_entry:.2f}."
                }

        cls.save_state(state, symbol=active_sym)

        return {
            "success": True,
            "msg": f"🎯 Trade #{t_num} Closed! Status: {status} • P&L: {closed_summary['pnl']}",
            "closed_trade": closed_summary,
            "state": state
        }

    @classmethod
    def acknowledge_and_reset(cls, symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        Rule 5: Wait for closure.
        User acknowledges closed trade outcome; transitions engine back to IDLE / SCANNING.
        """
        state = cls.get_state(symbol=symbol)
        state["current_state"] = cls.STATE_IDLE
        cls.save_state(state, symbol=symbol)
        return {
            "success": True,
            "msg": "✅ Trade acknowledged and logged. Engine is now in IDLE / SCANNING for next high-probability setup.",
            "state": state
        }

    @classmethod
    def get_running_trade_log_rows(cls, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Generates the EXACT running log table requested for the active scrip:
        Trade # | Instrument | Planned Entry | Actual Groww Entry | Executed (Yes/No) | SL | Target | Status (Open / Target Hit / SL Hit) | P&L
        """
        today_str = datetime.now(IST).strftime("%Y-%m-%d")
        sym_canon = resolve_symbol(symbol)
        sym_kw = "ADANI" if sym_canon == "ADANIENT" else sym_canon
        journal = TradeJournalManager.load_journal(symbol=sym_canon)

        # Strictly trades for this symbol for today
        today_trades = [
            t for t in journal 
            if t.get("date") == today_str and (sym_kw in str(t.get("trading_symbol", "")).upper() or sym_kw in str(t.get("instrument", "")).upper())
        ]
        # If no trades have been executed yet today, display recent verified trades from earlier sessions for this symbol
        is_prior_session = False
        if not today_trades:
            today_trades = [
                t for t in journal 
                if sym_kw in str(t.get("trading_symbol", "")).upper() or sym_kw in str(t.get("instrument", "")).upper()
            ][-5:]
            if today_trades:
                is_prior_session = True

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

            conf_val = tr.get("confluence_score")
            conf_str = f"{float(conf_val):.1f}%" if conf_val is not None else "—"
            trade_lbl = f"Trade {i}" if not is_prior_session else f"Trade {i} ({tr.get('date', '')})"

            rows.append({
                "Trade #": trade_lbl,
                "Date": tr.get("date", today_str),
                "Instrument": tr.get("instrument") or tr.get("trading_symbol") or f"{sym_kw} {tr.get('suggested_contract')}",
                "Confluence": conf_str,
                "Planned Entry": f"₹{float(tr.get('suggested_entry', 0.0)):.2f}",
                "Actual Groww Entry": f"₹{float(tr.get('actual_entry_price', tr.get('entry_price', 0.0))):.2f}",
                "Executed (Yes/No)": "Yes",
                "SL": f"₹{float(tr.get('suggested_sl', 0.0)):.2f}",
                "Target": f"₹{float(tr.get('suggested_exit', 0.0)):.2f}",
                "Status": status_label,
                "P&L": pnl_str
            })

        # If there is currently an active trade genuinely executed on Groww and not yet closed in journal, append it
        state = cls.get_state(symbol=symbol)
        curr_state = state.get("current_state")
        active = state.get("active_trade")
        if active and curr_state == cls.STATE_IN_TRADE and active.get("executed") == "Yes":
            active_inst = str(active.get("instrument", "")) + " " + str(active.get("contract", ""))
            if sym_kw in active_inst.upper():
                t_idx = int(active.get("trade_num") or (len(rows) + 1))
                already_in_rows = any(r.get("Trade #") == f"Trade {t_idx}" for r in rows)
                if not already_in_rows:
                    act_entry = f"₹{float(active.get('actual_entry', 0.0)):.2f}"
                    status_lbl = "Open"
                    unreal = float(active.get("unrealized_pnl", 0.0))
                    pnl_lbl = f"{'+' if unreal >= 0 else ''}₹{unreal:,.2f} (Live)"
                    executed_lbl = "Yes"
                    conf_act = active.get("confluence_score") or active.get("confluence") or 75.0
                    conf_act_str = f"{float(conf_act):.1f}%"

                    rows.append({
                        "Trade #": f"Trade {t_idx}",
                        "Date": today_str,
                        "Instrument": active.get("instrument", active.get("contract", "")),
                        "Confluence": conf_act_str,
                        "Planned Entry": f"₹{float(active.get('planned_entry', 0.0)):.2f}",
                        "Actual Groww Entry": act_entry,
                        "Executed (Yes/No)": executed_lbl,
                        "SL": f"₹{float(active.get('sl', 0.0)):.2f}",
                        "Target": f"₹{float(active.get('target', 0.0)):.2f}",
                        "Status": status_lbl,
                        "P&L": pnl_lbl
                    })

        return rows

